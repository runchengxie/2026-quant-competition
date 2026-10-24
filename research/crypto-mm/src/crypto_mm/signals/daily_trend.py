"""Historical daily trend and hysteresis definitions, without portfolio replay."""

import math


def hysteresis_states(prices):
    active = False
    states = []
    for i, close in enumerate(prices):
        if i >= 199:
            average = sum(prices[i - 199 : i + 1]) / 200
            if close > 1.02 * average:
                active = True
            elif close < 0.98 * average:
                active = False
        states.append(active)
    return states


def select_trend_products(closes, products, decision):
    selected = []
    for product in products:
        average = sum(closes[product][decision - 199 : decision + 1]) / 200
        if not math.isfinite(average):
            raise ValueError("INVALID_CONTROL_TREND_AVERAGE")
        if closes[product][decision] > average:
            selected.append(product)
    return selected
