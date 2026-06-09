# -*- coding: utf-8 -*-
import mod.client.extraClientApi as clientApi
import math, random
math.abs = abs
math.min = min
math.max = max

class SafeEvalError(Exception):
    pass

class Variable(object):
    def __init__(self, startTick=-1):
        if startTick == -1:
            startTick = globalTick
        self.__startTick = startTick

    @property
    def emmiter_age(self):
        return globalTick - self.__startTick
    

class ExpressionString(object):

    def __init__(self, expression):
        self.expression = expression

    def eval(self, variable, localVars={}):
        for k, v in localVars.items():
            setattr(variable, k, v)
        v = variable  # 别名

        # ---------------- Tokenizer ----------------
        def _is_digit(c):
            return '0' <= c <= '9'

        def _is_alpha(c):
            return ('a' <= c <= 'z') or ('A' <= c <= 'Z') or (c == '_')

        def _tokenize(s):
            tokens = []
            i, n = 0, len(s)

            while i < n:
                c = s[i]

                # whitespace
                if c in ' \t\r\n':
                    i += 1
                    continue

                # numbers: 12 / 12.34 / .5 (only if '.' followed by digit) / 5.
                if _is_digit(c) or (c == '.' and (i + 1 < n and _is_digit(s[i + 1]))):
                    j = i
                    dot = 0
                    if s[j] == '.':
                        dot = 1
                        j += 1
                    while j < n and (_is_digit(s[j]) or s[j] == '.'):
                        if s[j] == '.':
                            dot += 1
                            if dot > 1:
                                raise SafeEvalError("Invalid number (two dots)")
                        j += 1
                    tokens.append(('NUM', float(s[i:j])))
                    i = j
                    continue

                # '.' for attribute access
                if c == '.':
                    tokens.append(('OP', '.'))
                    i += 1
                    continue

                # identifiers
                if _is_alpha(c):
                    j = i + 1
                    while j < n and (_is_alpha(s[j]) or _is_digit(s[j])):
                        j += 1
                    tokens.append(('ID', s[i:j]))
                    i = j
                    continue

                # operators and punctuation
                if s.startswith('**', i):
                    tokens.append(('OP', '**'))
                    i += 2
                    continue

                if c in '+-*/(),':
                    tokens.append(('OP', c))
                    i += 1
                    continue

                if c in '()':
                    tokens.append(('OP', c))
                    i += 1
                    continue

                raise SafeEvalError("Unexpected char: %r" % c)

            tokens.append(('EOF', None))
            return tokens

        # ---------------- Parser / Evaluator ----------------
        #
        # Grammar:
        #   expr   := term (('+'|'-') term)*
        #   term   := power (('*'|'/') power)*
        #   power  := unary ('**' power)?          # right-associative
        #   unary  := ('+'|'-') unary | postfix
        #   postfix:= primary (('.' ID) | call )*
        #   call   := '(' [expr (',' expr)*] ')'
        #   primary:= NUM | ID | '(' expr ')'

        class _Parser(object):
            def __init__(self, tokens, var_obj):
                self.toks = tokens
                self.pos = 0
                self.var = var_obj

            def _peek(self):
                return self.toks[self.pos]

            def _eat(self, typ=None, val=None):
                t = self._peek()
                if typ is not None and t[0] != typ:
                    raise SafeEvalError("Expected %s, got %s" % (typ, t[0]))
                if val is not None and t[1] != val:
                    raise SafeEvalError("Expected %r, got %r" % (val, t[1]))
                self.pos += 1
                return t

            def parse(self):
                out = self._expr()
                self._eat('EOF', None)
                return out

            def _expr(self):
                val = self._term()
                while True:
                    t = self._peek()
                    if t == ('OP', '+'):
                        self._eat('OP', '+')
                        val = val + self._term()
                    elif t == ('OP', '-'):
                        self._eat('OP', '-')
                        val = val - self._term()
                    else:
                        break
                return val

            def _term(self):
                val = self._power()
                while True:
                    t = self._peek()
                    if t == ('OP', '*'):
                        self._eat('OP', '*')
                        val = val * self._power()
                    elif t == ('OP', '/'):
                        self._eat('OP', '/')
                        val = val / self._power()
                    else:
                        break
                return val

            def _power(self):
                val = self._unary()
                if self._peek() == ('OP', '**'):
                    self._eat('OP', '**')
                    rhs = self._power()
                    val = val ** rhs
                return val

            def _unary(self):
                t = self._peek()
                if t == ('OP', '+'):
                    self._eat('OP', '+')
                    return +self._unary()
                if t == ('OP', '-'):
                    self._eat('OP', '-')
                    return -self._unary()
                return self._postfix()

            def _postfix(self):
                obj = self._primary()
                last_attr_base = None

                while True:
                    t = self._peek()

                    # attribute access
                    if t == ('OP', '.'):
                        base = obj
                        self._eat('OP', '.')
                        name = self._eat('ID')[1]
                        if name.startswith('__'):
                            raise SafeEvalError("Dunder attribute not allowed: %s" % name)
                        try:
                            obj = getattr(base, name)
                        except AttributeError:
                            raise SafeEvalError("No such attribute: %s" % name)

                        last_attr_base = base
                        continue

                    if t == ('OP', '('):
                        if last_attr_base is not math and last_attr_base is not random:
                            raise SafeEvalError("Only math.xxx(...) or random.xxx(...) calls are allowed")
                        args = self._call_args()
                        obj = obj(*args)
                        last_attr_base = None
                        continue

                    break

                return obj

            def _call_args(self):
                self._eat('OP', '(')
                args = []
                if self._peek() != ('OP', ')'):
                    args.append(self._expr())
                    while self._peek() == ('OP', ','):
                        self._eat('OP', ',')
                        args.append(self._expr())
                self._eat('OP', ')')
                return args

            def _primary(self):
                t = self._peek()

                if t[0] == 'NUM':
                    return self._eat('NUM')[1]

                if t[0] == 'ID':
                    name = self._eat('ID')[1]
                    if name == 'math':
                        return math
                    if name == 'random':
                        return random
                    if name == 'v' or name == 'variable':
                        return self.var
                    raise SafeEvalError("Name not allowed: %s" % name)

                if t == ('OP', '('):
                    self._eat('OP', '(')
                    val = self._expr()
                    self._eat('OP', ')')
                    return val

                raise SafeEvalError("Unexpected token: %r" % (t,))

        tokens = _tokenize(self.expression)
        return _Parser(tokens, v).parse()

globalTick = 0

def setGlobalTime():
    global globalTick
    globalTick += 1

clientApi.GetEngineCompFactory().CreateGame(clientApi.GetLevelId()).AddRepeatedTimer(0.05, setGlobalTime)
