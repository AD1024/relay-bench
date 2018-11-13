from tvm.relay import Var, TypeVar
from typing import Any, Optional, List, Tuple
import attr

class LittleCppNode:
    pass

@attr.s(auto_attribs=True)
class Decl(LittleCppNode):
    bindings: List[Tuple[Var, LittleCppNode]]
    body: LittleCppNode

@attr.s(auto_attribs=True)
class PackedCall(LittleCppNode):
    name: str
    arity: int
    args: Any
    output_type: Any
    args_is_tuple: bool

@attr.s(auto_attribs=True)
class Invoke(LittleCppNode):
    call: Any
    args: Any

@attr.s(auto_attribs=True)
class CPPFunction(LittleCppNode):
    params: List[Var]
    body: Any
    ret_type: Any
    name: Optional[str] = None

@attr.s(auto_attribs=True)
class CPPIf(LittleCppNode):
    cond: Any
    true_branch: Any
    false_branch: Any
    relay_type: Any

@attr.s(auto_attribs=True)
class CPPTuple(LittleCppNode):
    fields: List[Any]
    relay_type: Any

@attr.s(auto_attribs=True)
class CPPMatch(LittleCppNode):
    data: Any
    clause: List[Tuple[Any, Any]]
    relay_type: Any

@attr.s(auto_attribs=True)
class CPPConstructor(LittleCppNode):
    tag: int
    fields: List[Any]
