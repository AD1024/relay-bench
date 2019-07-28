#!/bin/bash
config_dir=$1
data_dir=$2

source $BENCHMARK_DEPS/bash/common.sh

include_shared_python_deps
add_to_pythonpath $(pwd)

python_run_trial "run_relay.py" $config_dir $data_dir
python_run_trial "run_nnvm.py" $config_dir $data_dir
python_run_trial "run_mxnet.py" $config_dir $data_dir
# tensorflow needs this variable set, not sure why it isn't
# sufficient to set this within Python
export CUDA_VISIBLE_DEVICES=0
python_run_trial "run_tf.py" $config_dir $data_dir
python_run_trial "run_pt.py" $config_dir $data_dir
