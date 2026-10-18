# Simulation assumptions

Order placement and cancellation default to 100 ms each. Maker fees default to zero, order quantity to 0.1, maximum inventory to 1.0, and tick size to 0.1. These are model parameters, not an exchange specification.

Public trade volume consumes the visible queue at a resting order price. Trades through an order price can fill the remaining order in full; this is a model assumption rather than an observed private execution. Price/time priority is simulated within the model. Cancellation and placement latency leave orders exposed until their scheduled transitions. Funding updates affect signals, not actual funding settlements. No hidden queue, exchange matching-engine validation, market impact, liquidation, margin, or broker connection is implemented.

Input streams must be sorted. Equal timestamps are processed in stages before strategy decisions. PnL depends on these assumptions and the chosen parameters. Tests validate software contracts and synthetic cases; they do not establish real-market profitability. Known sampling-label and non-finite audit limitations are listed in the README.
