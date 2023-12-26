from collections import Counter

import numpy as np
import pandas as pd


def poly_features(
        data: pd.DataFrame | dict[str, list | np.ndarray | int | float],
        degree: int = 3,
        simplified_name: bool = True
) -> dict[str, np.ndarray | int | float]:
    expression = data.keys()

    for _ in expression:
        if ' * ' in _:
            raise KeyError(f'The data can not have " * " in this keys or columns. Invalid name: {_}')

    extended_names = [[_] for _ in expression]
    extended_features = {}

    if degree <= 1:
        return data

    for i in range(1, degree):  # 0, 1, 2
        extended_orders = []
        for new_term in expression[:]:  # x1
            t = extended_names[:]  # [['x1'], ['x2'], ['x3']]
            for original_term in t:
                extended_orders.append(original_term + [new_term])  # [['x1', 'x1'], ['x2', 'x1'], ['x3', 'x1']]
        extended_names = extended_orders
    extended_names = sorted(set([' * '.join(sorted(_)) for _ in extended_names]))

    for expression in extended_names:
        features = expression.split(' * ')
        value = 1

        for feature in features:
            _ = np.array(data[feature])
            value *= _

        if simplified_name:
            terms = expression.split(' * ')
            sorted_terms = sorted(terms)
            term_counts = Counter(sorted_terms)
            expression = ' * '.join([f'{term}^{count}' if count > 1 else term for term, count in term_counts.items()])

        extended_features[expression] = value

    return extended_features
