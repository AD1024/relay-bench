from io import open
import glob
import os
import random
import unicodedata
import string
import time
import math
from rnn.language_data import N_CATEGORIES
from rnn.relay.util import categoryTensor, inputTensor
import numpy as np
import tvm
from tvm import relay
from tvm.relay import op
from tvm.relay import create_executor, Module
from tvm.relay.backend.interpreter import TensorValue
from tvm.relay.prelude import Prelude
from aot import aot

def linear(input_size, output_size, x, name=None):
    if name is None:
        name = ""

    weight = relay.var(f'{name}linear_weight', shape=(output_size, input_size))
    bias = relay.var(f'{name}linear_bias', shape=(output_size,))
    return op.add(op.nn.dense(x, weight), bias)

def initialize(param):
    ty = param.type_annotation
    shape = [int(i) for i in ty.shape]
    return TensorValue(
        np.random.normal(0, 1, shape).astype('float32'))

class Network:
    def __init__(self, *args):
        self.mod = Module()
        self.prelude = Prelude(self.mod)
        self.context = tvm.cpu(0)
        self.target = tvm.target.create('llvm')
        self.executor = create_executor(mod=self.mod, ctx=self.context)
        self.parameters = {}

        # Set up forward pass.
        inputs, body = self.compute(*args)
        self.inputs = inputs

        free_vars = relay.ir_pass.free_vars(body)
        for param in free_vars[len(inputs):]:
            self.parameters[param] = initialize(param)
        self.hidden = initialize(free_vars[2])
        self.forward_compute = relay.Function(free_vars, body)
        self.forward = aot.compile(self.mod, self.forward_compute)
        #self.forward = self.executor.static_evaluate(self.forward_compute)
        self.args = [None] * len(inputs) + list(self.parameters.values())

    def __call__(self, *inputs):
        for i, inp in enumerate(inputs):
            self.args[i] = inp

        return self.forward(*self.args)

class RNNCellOnly(Network):
    def compute(self, input_size, hidden_size, output_size):
        self.category_var = category = relay.var('category', shape=(1, N_CATEGORIES))
        self.input_var = inp = relay.var('input', shape=(1, input_size))
        self.hidden_var = hidden = relay.var('hidden', shape=(1, hidden_size))
        combined = op.concatenate([category, inp, hidden], axis=1)
        hidden = linear(N_CATEGORIES + input_size + hidden_size, hidden_size, combined, name='i2h')
        output = linear(N_CATEGORIES + input_size + hidden_size, output_size, combined, name='i2o')
        output_combined = op.concatenate([hidden, output], axis=1)
        output = linear(hidden_size + output_size, output_size, output_combined, name='o2o')
        #output = op.nn.dropout(output, 0.1) #dropout isnt simplified, commented out for now
        output = op.nn.log_softmax(output, axis=1)
        return [category, inp, hidden], relay.Tuple([output, hidden])

    def warm(self):
        self.forward(initialize(self.category_var), initialize(self.input_var), initialize(self.hidden_var), *self.parameters.values())

# class RNNLoop:
#     def __init__(self, input_size, hidden_size, output_size):
#         mod = Module()
#         p = Prelude(mod)
#         ctx = tvm.context("llvm", 0)
#         intrp = create_executor(mod=mod, ctx=ctx, target="llvm")
#         self.fwd = relay.GlobalVar('fwd')
#         self.hidden = init((1, hidden_size))
#         category = relay.var('category', shape=(1, data.N_CATEGORIES))
#         n_letter = relay.const(data.N_LETTERS)
#         one_diag = relay.const(np.diag(np.ones(58)).astype('float32'))
#         boxed_one = relay.const(np.array([1]).astype('int32'))
#         inp_topi = relay.var('input', shape=(), dtype='int32')
#         inp = op.take(one_diag, op.multiply(boxed_one, inp_topi), axis=0)
#         hidden_var = relay.var('hidden', shape=(1, hidden_size))
#         combined = op.concatenate([category, inp, hidden_var], axis=1)
#         hidden, self.w0_var, self.b0_var = linear(data.N_CATEGORIES + input_size + hidden_size, hidden_size, combined)
#         output, self.w1_var, self.b1_var = linear(data.N_CATEGORIES + input_size + hidden_size, output_size, combined)
#         output_combined = op.concatenate([hidden, output], axis=1)
#         output, self.w2_var, self.b2_var = linear(hidden_size + output_size, output_size, output_combined)
#         # output = op.nn.dropout(output, 0.1) #attributes has not been registered
#         output = op.nn.log_softmax(output, axis=1)
#         topi = op.argmax(output)
#         body = relay.Tuple([output,
#                             hidden,
#                             topi,
#                             op.equal(topi, op.subtract(n_letter, relay.const(1)))])
#         assert len(relay.ir_pass.free_vars(body)) == 9
#         inp_para = [category, inp_topi, hidden_var]
#         weight_para = [self.w0_var, self.b0_var, self.w1_var, self.b1_var, self.w2_var, self.b2_var]
#         para = inp_para + weight_para
#         self.w0 = init((data.N_CATEGORIES + input_size + hidden_size, hidden_size))
#         self.b0 = init(hidden_size)
#         self.w1 = init((data.N_CATEGORIES + input_size + hidden_size, output_size))
#         self.b1 = init(output_size)
#         self.w2 = init((hidden_size + output_size, output_size))
#         self.b2 = init(output_size)
#         mod[self.fwd] = relay.Function(para, body)
#         self.forward = intrp.static_evaluate(self.fwd)

#         self.loop_fwd = relay.GlobalVar('loop_fwd')
#         max = relay.var('max', shape=(), dtype='int32')
#         loop_para = [max] + para
#         fwd_res = self.fwd(*para)
#         else_else_branch = p.cons(fwd_res[2], self.loop_fwd(op.subtract(max, relay.const(1)), category, fwd_res[2], fwd_res[1], *weight_para))
#         else_branch = relay.If(fwd_res[3], p.nil(), else_else_branch)
#         body = relay.If(op.equal(max, relay.const(0)), p.nil(), else_branch)
#         mod[self.loop_fwd] = relay.Function(loop_para, body)
#         print(mod[self.loop_fwd].checked_type)
#         self.loop_forward = intrp.static_evaluate(self.loop_fwd)

#     def __call__(self, category, input, hidden):
#         return self.forward(category, input, hidden, self.w0, self.b0, self.w1, self.b1, self.w2, self.b2)

#     def woosh(self, l):
#         if l.con.name_hint == 'cons':
#             return [np.asscalar(l.fields[0].data.asnumpy())] + self.woosh(l.fields[1])
#         else:
#             assert l.con.name_hint == 'nil'
#             return []

#     def sample(self, category, start_letter='A'):
#         category_tensor = categoryTensor(category)
#         input = data.letter_to_topi(start_letter)
#         hidden = self.hidden
#         output = self.loop_forward(20,
#                                    category_tensor,
#                                    input,
#                                    hidden,
#                                    self.w0,
#                                    self.b0,
#                                    self.w1,
#                                    self.b1,
#                                    self.w2,
#                                    self.b2)
#         output_name = ''
#         for x in [data.letter_to_topi(start_letter)] + self.woosh(output):
#             output_name += data.topi_to_letter(x)
#         return output_name

#     #def sample(self, category, start_letter='A'):
#     #    category_tensor = categoryTensor(category)
#     #    input = data.letter_to_topi(start_letter)
#     #    hidden = self.hidden
#     #    output_topi = [relay.const(data.letter_to_topi(start_letter))]
#     #    for i in range(data.MAX_LENGTH):
#     #        output, hidden, input, b = self.forward(category_tensor,
#     #                                                input,
#     #                                                hidden,
#     #                                                self.w0,
#     #                                                self.b0,
#     #                                                self.w1,
#     #                                                self.b1,
#     #                                                self.w2,
#     #                                                self.b2)
#     #        if b.data.asnumpy():
#     #            break
#     #        else:
#     #            output_topi.append(input)
#     #    output_name = ''
#     #    for x in output_topi:
#     #        output_name += data.topi_to_letter(x.data.asnumpy())
#     #    return output_name

#     def samples(self, category, start_letters='ABC'):
#         for start_letter in start_letters:
#             print(self.sample(category, start_letter))
