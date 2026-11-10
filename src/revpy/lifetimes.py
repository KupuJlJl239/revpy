from __future__ import annotations
from dataclasses import dataclass
from typing import Iterable

from .base import RevpyCompilationError



###########################
###   LIFETIME CHECKS   ###
###########################


@dataclass
class VariableSideUsage:
    name: str
    exists: bool
    usage: str

    def match(self, other: VariableSideUsage) -> None:
        assert self.name == other.name
        if self.exists != other.exists:
            raise RevpyCompilationError(f"Lifetime error: variable '{self.name}'\n\t--> {self.usage}\n\t--> {other.usage} ")

@dataclass
class VariableUsage:
    start: VariableSideUsage
    end: VariableSideUsage 
    own: bool

    def __add__(self, other: VariableUsage) -> VariableUsage:
        self.end.match(other.start)
        return VariableUsage(self.start, other.end, self.own | other.own)
    
    def __or__(self, other: VariableUsage) -> VariableUsage:
        self.start.match(other.start)
        self.end.match(other.end)
        return VariableUsage(self.start, other.end, self.own | other.own)
    
    @property
    def rev(self):
        return VariableUsage(start=self.end, end=self.start, own=self.own)
    
    def check(self) -> VariableUsage:
        assert self.start.name == self.end.name
        if self.start.exists != self.end.exists:
            raise RevpyCompilationError(f"Lifetime error: variable '{self.start.name}' must both exist or both not exist\n\t--> {self.start.usage}\n\t--> {self.end.usage} ")
        return self



def unite_dicts(A, B, unary_op, binary_op):
    common = {k: binary_op(A[k], B[k]) for k in A.keys() & B.keys()}
    non_common = {k: unary_op(v) for k, v in (A | B).items() if not k in (A.keys() & B.keys())}
    return common | non_common

@dataclass
class Signature:
    dct: dict[str, VariableUsage]

    def __add__(self, other: Signature) -> Signature:
        return Signature(unite_dicts(self.dct, other.dct, unary_op=lambda x: x, binary_op=VariableUsage.__add__))
    
    def __or__(self, other: Signature) -> Signature:
        return Signature(unite_dicts(self.dct, other.dct, unary_op=VariableUsage.check, binary_op=VariableUsage.__or__))
    
    @staticmethod
    def from_line(input: Iterable[str], output: Iterable[str], capture: Iterable[str], line: str) -> Signature:
        IN = set(input)
        OUT = set(output)
        if len(IN) != len(input):
            raise RevpyCompilationError(f"Some destroyed names repeat! Line:\n{line}\n")
        if len(OUT) != len(output):
            raise RevpyCompilationError(f"Some created names repeat! Line:\n{line}\n")
        C = set(capture)
        if not C.isdisjoint(IN):
            raise RevpyCompilationError(f"Some names are destroyed and captured at the same time: {C & IN}! Line:\n{line}\n")
        if not C.isdisjoint(OUT):
            raise RevpyCompilationError(f"Some names are created and captured at the same time: {C & OUT}! Line:\n{line}\n")\
        
        return Signature({
            k: VariableUsage(
                start=VariableSideUsage(name=k, exists=k in IN | C, usage=line),
                end=VariableSideUsage(name=k, exists=k in OUT | C, usage=line),
                own=k not in C
            ) 
            for k in IN | OUT | C   # k -- имя переменной
        })
    
    @property
    def rev(self):
        return Signature({k: v.rev for k, v in self.dct.items()})
    
    @property
    def names_input(self):
        return set([k for k, v in self.dct.items()  if v.start.exists and v.own])
    
    @property
    def names_output(self):
        return set([k for k, v in self.dct.items()  if v.end.exists and v.own])
    
    @property
    def names_capture(self):
        return set([k for k, v in self.dct.items() if not v.own])
    
    @property
    def names_local(self):
        return set([k for k, v in self.dct.items()  if v.own])
    
    @property
    def names_all(self):
        return set([k for k, v in self.dct.items() ])