from itertools import chain

import torch
from torch.autograd import Function

from .._ext import ffi


def _scatter(name, dim, *data):
    a, b, c = data[:3]

    # Assert same dimensionality across all inputs.
    assert dim >= 0 and dim < a.dim(), 'Index dimension is out of bounds'
    assert b.dim() == c.dim(), ('Index tensor must have same dimensions as '
                                'input tensor')
    assert a.dim() == c.dim(), ('Input tensor must have same dimensions as '
                                'output tensor')

    # Assert same tensor length across index and input.
    assert b.numel() == c.numel(), ('Index tensor must have same size as '
                                    'input tensor')

    # Assert same tensor sizes across input and output apart from `dim`.
    for d in chain(range(dim), range(dim + 1, a.dim())):
        assert a.size(d) == c.size(d), (
            'Input tensor must have same size as output tensor apart from the '
            'specified dimension')

    typename = type(data[0]).__name__.replace('Tensor', '')
    func = getattr(ffi, 'scatter_{}_{}'.format(name, typename))
    func(dim, *data)


class _Scatter(Function):
    def __init__(self, name, dim):
        super(_Scatter, self).__init__()
        self.name = name
        self.dim = dim

    def forward(self, *data):
        assert not self.needs_input_grad[1], 'Can\'t differentiate the index'

        self.mark_dirty(data[0])  # Mark output as dirty.
        self.len = len(data)  # Save number of arguments for backward step
        self.save_for_backward(data[1])  # Save index for backward step.

        _scatter(self.name, self.dim, *data)
        return data[0]

    def backward(self, *data):
        index, = self.saved_variables
        grad_output = grad_input = None

        if self.needs_input_grad[0]:
            grad_output = data[0]
        if self.needs_input_grad[2]:
            # TODO: max and min
            grad_input = data[0].gather(self.dim, index.data)

        return (grad_output, None, grad_input) + (None, ) * (self.len - 3)


def scatter(name, dim, *data):
    if torch.is_tensor(data[0]):
        return _scatter(name, dim, *data)
    else:
        return _Scatter(name, dim)(*data)