"""Benchmark script for ImageNet models on ARM CPU.
see README.md for the usage and results of this script.
"""
import argparse

import numpy as np

import tvm
from tvm import relay
from tvm.contrib.util import tempdir
import tvm.contrib.graph_runtime as runtime
import nnvm.compiler
import nnvm.testing

from util import get_network, print_progress

def build_nnvm_network(network, target, target_host):
    net, params, input_shape = get_network(network, batch_size=1, ir="nnvm")

    print_progress("%-20s nnvm building..." % network)
    with nnvm.compiler.build_config(opt_level=3):
        graph, lib, params = nnvm.compiler.build(
            net, target=target, target_host=target_host,
            shape={'data': input_shape}, params=params, dtype=dtype)

    return net, params, input_shape, graph, lib

def build_relay_network(network, target, target_host):
    net, params, input_shape = get_network(network, batch_size=1, ir="relay")

    print_progress("%-20s relay building..." % network)
    with relay.build_module.build_config(opt_level=3):
        graph, lib, params = relay.build(net, target=target, target_host=target_host, params=params)

    return net, params, input_shape, graph, lib

def build_module(network, target, target_host, ir="relay"):
    # connect to remote device
    tracker = tvm.rpc.connect_tracker(args.host, args.port)
    remote = tracker.request(args.rpc_key)

    print_progress(network)
    if ir == "relay":
        net, params, input_shape, graph, lib = build_relay_network(network, target, target_host)
    elif ir == "nnvm":
        net, params, input_shape, graph, lib = build_nnvm_network(network, target, target_host)
    else:
        raise Exception("ir must be `relay` or `nnvm`, but you used `{}`".format(ir))

    tmp = tempdir()
    if 'android' in str(target):
        from tvm.contrib import ndk
        filename = "%s.so" % network
        lib.export_library(tmp.relpath(filename), ndk.create_shared)
    else:
        filename = "%s.tar" % network
        lib.export_library(tmp.relpath(filename))

    # upload library and params
    print_progress("%-20s uploading..." % network)
    ctx = remote.context(str(target), 0)
    remote.upload(tmp.relpath(filename))

    if isinstance(graph, nnvm.graph.Graph):
        with open("nnvm_graph.json", "w") as outf:
            print(graph.json(), file=outf)
    else:
        with open("relay_graph.json", "w") as outf:
            print(graph, file=outf)

    rlib = remote.load_module(filename)
    module = runtime.create(graph, rlib, ctx)
    data_tvm = tvm.nd.array((np.random.uniform(size=input_shape)).astype(dtype))
    module.set_input('data', data_tvm)
    module.set_input(**params)

    # evaluate
    return module, ctx

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--network", type=str, choices=
                        ['resnet-18', 'resnet-34', 'resnet-50',
                         'vgg-16', 'vgg-19', 'densenet-121', 'inception_v3',
                         'mobilenet', 'mobilenet_v2', 'squeezenet_v1.0', 'squeezenet_v1.1', 'mlp', 'custom', 'dqn', 'dcgan'],
                        help='The name of neural network')
    parser.add_argument("--model", type=str, choices=
                        ['llvm'], default='llvm',
                        help="The model of the test device. If your device is not listed in "
                             "the choices list, pick the most similar one as argument.")
    parser.add_argument("--host", type=str, default='localhost')
    parser.add_argument("--port", type=int, default=9190)
    parser.add_argument("--rpc-key", type=str, required=True)
    parser.add_argument("--repeat", type=int, default=10)
    parser.add_argument("--ir", type=str, choices=['relay', 'nnvm'], required=True)
    parser.add_argument("--output", type=str, choices=['eval', 'time'], required=True)
    args = parser.parse_args()

    dtype = 'float32'

    if args.network is None:
        networks = ['squeezenet_v1.1', 'mobilenet', 'resnet-18', 'vgg-16']
    else:
        networks = [args.network]

    target = tvm.target.arm_cpu(model=args.model)
    target_host = None

    print("--------------------------------------------------")
    print("%-20s %-20s" % ("Network Name", "Mean Inference Time (std dev)"))
    print("--------------------------------------------------")
    for network in networks:
        module, ctx = build_module(network, target, target_host, ir=args.ir)

        if args.output == "eval":
            print_progress("%-20s evaluating..." % network)
            module.run()
            output = module.get_output(0)
            print(output)
            print(output.shape)
        elif args.output == "time":
            print_progress("%-20s evaluating..." % network)
            ftimer = module.module.time_evaluator("run", ctx, number=1, repeat=args.repeat)
            prof_res = np.array(ftimer().results) * 1000  # multiply 1000 for converting to millisecond
            print("%-20s %-19s (%s)" % (network, "%.2f ms" % np.mean(prof_res), "%.2f ms" % np.std(prof_res)))
        else:
            assert False
