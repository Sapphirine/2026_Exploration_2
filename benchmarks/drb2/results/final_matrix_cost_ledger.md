# DRB-II compute & cost ledger

DeepSeek pricing assumed: $0.27/M input, $1.10/M output. Costs cover the **judge** only — agent calls during runs are not summed here.

| Label | Run min | Judge in tok | Judge out tok | Judge $ |
|---|---|---|---|---|
| evoresearcher | 14.6 | 46,547 | 27,239 | $0.04 |
| evoresearcher_blind_n3 | 48.0 | 152,349 | 84,283 | $0.13 |
| evoresearcher_n3 | 47.3 | 152,841 | 85,872 | $0.14 |
| evoresearcher_noelo_n3 | 40.5 | 151,293 | 85,070 | $0.13 |
| evoresearcher_warm_n3 | 41.6 | 157,002 | 88,682 | $0.14 |
| qwen3_max | 0.0 | 174,728 | 38,474 | $0.09 |
| TOTAL | 192.0 | 834,760 | 409,620 | $0.68 |
