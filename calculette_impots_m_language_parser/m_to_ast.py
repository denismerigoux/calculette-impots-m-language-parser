
"""
Convert M language source code to a JSON AST. All the information is kept. Loops are not unfolded.
"""


from collections import OrderedDict
import logging
import os
import sys
import re

from arpeggio import PTNodeVisitor, visit_parse_tree
from arpeggio.cleanpeg import ParserPEG
from toolz import concatv, pluck

from calculette_impots_m_language_parser import json_dump


# Globals

debug = False

log = logging.getLogger()
logging.basicConfig(level=logging.DEBUG if debug else logging.WARNING, stream=sys.stdout)

script_dir_path = os.path.dirname(os.path.abspath(__file__))
m_grammar_file_path = os.path.join(script_dir_path, 'm_language.cleanpeg')
with open(m_grammar_file_path) as m_grammar_file:
    m_grammar = m_grammar_file.read()
root_rule = 'm_source_file'
m_parser = ParserPEG(m_grammar, root_rule, debug=debug, reduce_tree=False)
log.debug('M language clean-PEG grammar was parsed with success.')


# Public functions

def parse_m_file(source_code):
    '''Parse a source code in language M and returns its Abstract Syntax Tree (AST)'''
    source_code = preprocess(source_code)
    parse_tree = m_parser.parse(source_code)
    result = visit_parse_tree(parse_tree, MLanguageVisitor(debug=debug))
    return json_dump.dumps(result)


# M CONSTANTS

M_ADDITION = '+'
M_SUBSTRACTION = '-'
M_MULTIPLICATION = '*'
M_DIVISION = '/'


# Helpers

def preprocess(source_code):
    lines = source_code.split('\n')

    inline_comment_regex = r'^([^#]+)#.*$'

    preprocessed_lines = []
    for line in lines:
        m = re.match(inline_comment_regex, line)
        if m:
            preprocessed_line = m.groups()[0]
        else:
            preprocessed_line = line
        preprocessed_lines.append(preprocessed_line)

    return '\n'.join(preprocessed_lines)

def extract_operators(node):
    return [
        node[index].value
        for index in range(1, len(node), 2)
        ]


def find(nodes, type):
    return [
        node
        for node in nodes
        if node['type'] == type
        ]


def find_one_or_many(nodes, type):
    results = find_many_or_none(nodes, type)
    assert results is not None and len(results) > 0, (nodes, type, results)
    return results


def find_many_or_none(nodes, type):
    return find(nodes, type) or None


def find_many(nodes, type):
    results = find_many_or_none(nodes, type)
    assert results is not None and len(results) > 1, (nodes, type, results)
    return results


def find_one(nodes, type):
    results = find_many_or_none(nodes, type)
    assert results is not None and len(results) == 1, (nodes, type, results)
    return results[0]


def find_one_or_none(nodes, type):
    results = find_many_or_none(nodes, type)
    assert results is None or len(results) == 1, (nodes, type, results)
    return results[0] if results else None


def get_linecol(node):
    global m_parser
    return (m_parser.pos_to_linecol(node.position), m_parser.pos_to_linecol(node[-1].position))


def make_node(node=None, linecol=None, type=None, **kwargs):
    clean_node = without_empty_values(
        linecol=(
            get_linecol(node)
            if node is not None and linecol
            else None
            ),
        type=(
            node.rule_name
            if type is None
            else type
            ),
        **kwargs
        )
    return pretty_ordered_keys(clean_node)


def make_nested_operators_ast_nodes(node, operators, operands, type):
    assert len(operands) > 1, operands
    return make_node(
        left_operand=operands[0],
        node=node,
        operator=operators[0],
        right_operand=operands[1]
        if len(operators) == 1
        else make_nested_operators_ast_nodes(node=node, operators=operators[1:], operands=operands[1:], type=type),
        type=type,
        )


def only_child(children):
    assert len(children) == 1, children
    return children[0]


def pretty_ordered_keys(dict_):
    """Order keys for the JSON to be more readable by a human."""
    def get_items(keys):
        return [(key, dict_[key]) for key in keys if key in dict_]
    assert isinstance(dict_, dict), dict_
    first_keys = ['type', 'name']
    last_keys = ['linecol']
    other_keys = sorted(set(dict_.keys()).difference(first_keys, last_keys))
    items = get_items(first_keys) + get_items(other_keys) + get_items(last_keys)
    return OrderedDict(items)


def to_list(value):
    return value if isinstance(value, list) else [value]


def without_empty_values(**kwargs):
    """Allows 0 values but not None, [], {}."""
    return {
        key: value
        for key, value in kwargs.items()
        if value is not None or isinstance(value, (list, dict)) and value
        }


# PEG parser visitor


class MLanguageVisitor(PTNodeVisitor):
    """
    Visitor class to transform AST in JSON.

    Useful line to debug visitor in ipython:
    print(node); node; len(node); print(json.dumps(children, indent=2)); len(children)
    """

    def visit__default__(self, node, children):
        """Ensure all grammar rules are implemented in visitor class."""
        if node.rule_name and node.rule_name != 'EOF':
            infos = {'rule': node.rule_name, 'node': node, 'children': children}
            raise NotImplementedError(infos)

    def visit_application(self, node, children):
        assert len(children) == 1, children
        return make_node(
            linecol=True,
            name=children[0]['value'],
            node=node,
            )

    def visit_applications_reference(self, node, children):
        assert len(children) == 1, children
        names = [symbol['value'] for symbol in children[0]]
        return make_node(
            names=names,
            node=node,
            )

    def visit_brackets(self, node, children):
        assert len(children) == 1, children
        return make_node(
            index=children[0]['value'],
            node=node,
            )

    def visit_comment(self, node, children):
        return None

    def visit_comparaison(self, node, children):
        if len(children) == 1:
            return children[0]
        else:
            operators = extract_operators(node)
            assert len(operators) == 1, operators
            assert len(children) == 2, children
            return make_node(
                left_operand=children[0],
                node=node,
                operator=operators[0],
                right_operand=children[1],
                )

    def visit_dans(self, node, children):
        if len(children) == 1:
            return children[0]
        else:
            assert len(children) == 2, children
            assert len(children[1]) == 1, children[1]
            return make_node(
                enumeration=children[1][0],
                expression=children[0],
                negative_form='non' in node or None,
                node=node,
                )

    def visit_enchaineur(self, node, children):
        assert len(children) == 2, children
        return make_node(
            applications=children[1]['names'],
            linecol=True,
            name=children[0]['value'],
            node=node,
            )

    def visit_enchaineur_reference(self, node, children):
        assert len(children) == 1, children
        return make_node(
            node=node,
            value=children[0]['value'],
            )

    def visit_enumeration(self, node, children):
        def iter_enumerations():
            integers_or_symbols = concatv(
                find(children, type='integer'),
                find(children, type='symbol'),
                )
            values = list(pluck('value', integers_or_symbols))
            if values:
                yield make_node(
                    type='enumeration_values',
                    values=values,
                    )
            intervals = find_many_or_none(children, type='interval')
            if intervals is not None:
                yield from intervals

        assert isinstance(children, list), children
        return list(iter_enumerations())

    def visit_enumeration_item(self, node, children):
        return only_child(children)

    def visit_erreur(self, node, children):
        erreur_type = find_one(children, type='erreur_type')['value']
        strings = [string['value'] for string in find_many(children, type='string')]
        nb_strings = len(strings)
        description = strings[3]
        codes = strings[:3] + ([strings[4]] if nb_strings == 5 else [])
        return make_node(
            codes=codes,
            description=description,
            erreur_type=erreur_type,
            linecol=True,
            name=children[0]['value'],
            node=node,
            )

    def visit_erreur_type(self, node, children):
        return make_node(
            node=node,
            value=node.value,
            )

    def visit_expression(self, node, children):
        if len(children) == 1:
            return children[0]
        else:
            operators = extract_operators(node)
            return make_node(
                node=node,
                operands=children,
                operators=operators,
                type='boolean_expression',
                )

    def visit_factor(self, node, children):
        if len(children) == 1:
            return children[0]
        else:
            if children[0]['type'] == 'sum_operator':
                result = children[1].copy()
                if result['type'] in ('float', 'integer'):
                    if children[0]['value'] == '-':
                        result['value'] = -result['value']
                else:
                    result = make_node(
                        expression=result,
                        node=node,
                        operator=children[0]['value'],
                        type='unary',
                        )
            else:
                result = children[0]
            return result

    def visit_factor_literal(self, node, children):
        assert len(children) == 1, children
        child = children[0]
        return make_node(type='integer', value=int(child['value'])) \
            if child['type'] == 'symbol' and child['value'].isdigit() \
            else child

    def visit_float(self, node, children):
        return make_node(
            node=node,
            value=float(node.value),
            )

    def visit_formula(self, node, children):
        brackets = find_one_or_none(children, type='brackets')
        return make_node(
            expression=children[-1],
            index=brackets['index'] if brackets is not None else None,
            linecol=True,
            name=children[0]['value'],
            node=node,
            )

    def visit_function_arguments(self, node, children):
        return children

    def visit_function_call(self, node, children):
        return make_node(
            arguments=to_list(children[1]),
            name=children[0]['value'],
            node=node,
            )

    def visit_group(self, node, children):
        return only_child(children)

    def visit_integer(self, node, children):
        return make_node(
            node=node,
            value=int(node.value),
            )

    def visit_interval(self, node, children):
        assert len(children) == 2, children
        return make_node(
            first=children[0]['value'],
            last=children[1]['value'],
            node=node,
            )

    def visit_loop_expression(self, node, children):
        assert len(children) == 2, children
        assert isinstance(children[0], list), children[0]
        return make_node(
            expression=children[1],
            loop_variables=children[0],
            node=node,
            )

    def visit_loop_variable1(self, node, children):
        assert len(children) == 2, children
        return make_node(
            enumerations=children[1],
            name=children[0]['value'],
            node=node,
            type='loop_variable',
            )

    def visit_loop_variable2(self, node, children):
        assert len(children) == 2, children
        return make_node(
            enumerations=children[1],
            name=children[0]['value'],
            node=node,
            type='loop_variable',
            )

    def visit_loop_variables(self, node, children):
        assert isinstance(children, list), children
        return children

    def visit_m_source_file(self, node, children):
        return children

    def visit_pour_formula(self, node, children):
        assert len(children) == 2, children
        assert isinstance(children[0], list), children[0]
        return make_node(
            formula=children[1],
            loop_variables=children[0],
            node=node,
            )

    def visit_product_expression(self, node, children):
        def iter_product(node, children):
            for index, _ in enumerate(node):
                # In the M language, the first operand is always multiplied, never divided
                if index == 0:
                    yield children[0]
                else:
                    if node[index].value == M_MULTIPLICATION:
                        yield children[index + 1]

        def iter_division(node, children):
            for index, _ in enumerate(node):
                if node[index].value == M_DIVISION:
                    yield children[index + 1]

        if len(children) == 1:
            return children[0]
        else:
            # With the M implementation, there is only one / which is always last, and there might be several *
            products = list(iter_product(node=node, children=children))
            divs = list(iter_division(node=node, children=children))

            operands = products + list(map(lambda x: make_node(operand=x, type='invert'), divs))

            return make_node(
                operands=operands,
                type='product',
                )

    def visit_product_operator(self, node, children):
        return make_node(
            node=node,
            value=node.value,
            )

    def visit_regle(self, node, children):
        applications = find_one(children, type='applications_reference')['names']
        enchaineur_reference = find_one_or_none(children, type='enchaineur_reference')
        symbols = find_one_or_many(children, type='symbol')
        name, tags = symbols[-1]['value'], symbols[:-1] or None
        formulas = find_many_or_none(children, type='formula')
        pour_formulas = find_many_or_none(children, type='pour_formula')
        all_formulas = ([] + (formulas or []) + (pour_formulas or [])) or None
        return make_node(
            applications=applications,
            enchaineur=enchaineur_reference['value'] if enchaineur_reference is not None else None,
            formulas=all_formulas,
            linecol=True,
            name=name,
            node=node,
            tags=tags,
            )

    def visit_string(self, node, children):
        return make_node(
            node=node,
            value=node[1].value,
            )

    def visit_sum_expression(self, node, children):
        def iter_positives(node):
            for index, _ in enumerate(node):
                # In M Language, the first operand is always positive
                if index == 0:
                    yield children[0]
                    # yield make_node(node=child)
                else:
                    if node[index].value == M_ADDITION:
                        yield children[index + 1]

        def iter_negatives(node):
            for index, _ in enumerate(node):
                # In M Language, negative values are never first operand
                if node[index].value == M_SUBSTRACTION:
                    yield children[index + 1]

        if len(children) == 1:
            return children[0]
        else:
            positives = list(iter_positives(node=node))
            negatives = list(iter_negatives(node=node))
            operands = positives + list(map(lambda x: make_node(operand=x, type='negate'), negatives))
            return make_node(
                operands=operands,
                type='sum',
                )

    def visit_sum_operator(self, node, children):
        return make_node(
            node=node,
            value=node.value,
            )

    def visit_symbol(self, node, children):
        return make_node(
            node=node,
            value=node.value,
            )

    def visit_symbol_enumeration(self, node, children):
        assert isinstance(children, list), children
        return children

    def visit_ternary_operator(self, node, children):
        if len(children) == 1:
            return children[0]
        else:
            return make_node(
                condition=children[0],
                node=node,
                value_if_false=children[2] if len(children) == 3 else None,
                value_if_true=children[1],
                )

    def visit_value_type(self, node, children):
        return make_node(
            name='type',
            node=node,
            value=node[1].value,
            )

    def visit_variable(self, node, children):
        return only_child(children)

    def visit_variable_calculee(self, node, children):
        description = find_one(children, type='string')['value']
        subtypes = find_many_or_none(children, type='variable_calculee_subtype') or []
        subtypes = sorted(pluck('value', subtypes))
        value_type = find_one_or_none(children, type='value_type')
        tableau = find_one_or_none(children, type='variable_calculee_tableau')
        return make_node(
            base=('base' in subtypes) or None,
            description=description,
            linecol=True,
            name=children[0]['value'],
            node=node,
            restituee=('restituee' in subtypes) or None,
            tableau=None if tableau is None else tableau['dimension'],
            value_type=None if value_type is None else value_type['value'],
            )

    def visit_variable_calculee_subtype(self, node, children):
        return make_node(
            node=node,
            value=node[0].value,
            )

    def visit_variable_calculee_tableau(self, node, children):
        assert len(children) == 1, children
        return make_node(
            dimension=children[0]['value'],
            node=node,
            )

    def visit_variable_const(self, node, children):
        assert len(children) == 2, children
        return make_node(
            linecol=True,
            name=children[0]['value'],
            node=node,
            value=children[1]['value'],
            )

    def visit_variable_saisie(self, node, children):
        description = find_one(children, type='string')['value']
        alias = find_one_or_none(children, type='variable_saisie_alias')
        attributes = find_many_or_none(children, type='variable_saisie_attribute')
        if attributes is not None:
            attributes = OrderedDict(sorted(
                (attribute['name'], attribute['value'])
                for attribute in attributes
                ))
        restituee = find_one_or_none(children, type='variable_saisie_restituee')
        subtype = find_one(children, type='variable_saisie_subtype')['value']
        value_type = find_one_or_none(children, type='value_type')
        return make_node(
            alias=None if alias is None else alias['value'],
            attributes=attributes,
            description=description,
            linecol=True,
            name=children[0]['value'],
            node=node,
            restituee=(restituee is None) or None,
            subtype=subtype,
            value_type=None if value_type is None else value_type['value'],
            )

    def visit_variable_saisie_alias(self, node, children):
        assert len(children) == 1, children
        return make_node(
            node=node,
            value=children[0]['value'],
            )

    def visit_variable_saisie_attribute(self, node, children):
        assert len(children) == 2, children
        return make_node(
            name=children[0]['value'],
            node=node,
            value=children[1]['value'],
            )

    def visit_variable_saisie_restituee(self, node, children):
        return make_node(
            node=node,
            value=node.value,
            )

    def visit_variable_saisie_subtype(self, node, children):
        return make_node(
            node=node,
            value=node[0].value,
            )

    def visit_verif(self, node, children):
        symbols = find_one_or_many(children, type='symbol')
        name, tags = symbols[-1]['value'], symbols[:-1] or None
        applications = find_one(children, type='applications_reference')['names']
        conditions = find_one_or_many(children, type='verif_condition')
        return make_node(
            applications=applications,
            conditions=conditions,
            linecol=True,
            name=name,
            node=node,
            tags=tags,
            )

    def visit_verif_condition(self, node, children):
        erreurs = [symbol['value'] for symbol in children[1:]]
        variable_name = erreurs[1] if len(erreurs) > 1 else None
        return make_node(
            error_name=erreurs[0],
            expression=children[0],
            node=node,
            variable_name=variable_name,
            )

    def visit_sortie(self, node, children):
        return make_node(
            node=node,
            variable_name=children[0]['value'],
            )