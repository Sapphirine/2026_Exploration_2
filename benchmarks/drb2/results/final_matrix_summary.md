# DRB-II pilot results (DeepSeek-as-judge)

## Per-label summary (mean ± std across tasks)

| Label | N | Info Recall | Analysis | Presentation | Total |
|---|---|---|---|---|---|
| evoresearcher | 5 | 4.8% ± 6.0 | 25.7% ± 33.0 | 76.3% ± 29.4 | 15.7% ± 11.5 |
| evoresearcher_blind_n3 | 15 | 13.5% ± 14.6 | 30.1% ± 26.7 | 78.1% ± 28.6 | 23.0% ± 15.9 |
| evoresearcher_n3 | 15 | 12.2% ± 9.6 | 23.4% ± 27.9 | 91.4% ± 14.8 | 21.8% ± 11.9 |
| evoresearcher_noelo_n3 | 15 | 8.9% ± 10.3 | 25.7% ± 29.2 | 76.3% ± 30.2 | 18.8% ± 14.0 |
| evoresearcher_warm_n3 | 15 | 13.1% ± 12.0 | 28.8% ± 26.1 | 81.3% ± 24.9 | 22.6% ± 14.2 |
| qwen3_max | 5 | 55.7% ± 39.6 | 62.9% ± 27.7 | 90.5% ± 14.7 | 60.6% ± 32.7 |

## Per-task breakdown

| Label | idx | Recall | Analysis | Presentation | Total | Rubrics |
|---|---|---|---|---|---|---|
| evoresearcher | 4 | 1.9% | 18.2% | 87.5% | 13.9% | 72 |
| evoresearcher | 16 | 13.5% | 83.3% | 100.0% | 34.6% | 52 |
| evoresearcher | 42 | 0.0% | 14.3% | 85.7% | 12.0% | 75 |
| evoresearcher | 52 | 8.6% | 0.0% | 83.3% | 14.5% | 55 |
| evoresearcher | 68 | 0.0% | 12.5% | 25.0% | 3.3% | 60 |
| evoresearcher_blind_n3 | 4 | 3.8% | 36.4% | 100.0% | 19.4% | 72 |
| evoresearcher_blind_n3 | 4 | 1.9% | 18.2% | 87.5% | 13.9% | 72 |
| evoresearcher_blind_n3 | 4 | 9.4% | 27.3% | 100.0% | 22.2% | 72 |
| evoresearcher_blind_n3 | 16 | 13.5% | 83.3% | 66.7% | 32.7% | 52 |
| evoresearcher_blind_n3 | 16 | 18.9% | 25.0% | 66.7% | 23.1% | 52 |
| evoresearcher_blind_n3 | 16 | 24.3% | 83.3% | 100.0% | 42.3% | 52 |
| evoresearcher_blind_n3 | 42 | 0.0% | 0.0% | 14.3% | 1.3% | 75 |
| evoresearcher_blind_n3 | 42 | 0.0% | 28.6% | 100.0% | 17.3% | 75 |
| evoresearcher_blind_n3 | 42 | 36.2% | 28.6% | 85.7% | 38.7% | 75 |
| evoresearcher_blind_n3 | 52 | 42.9% | 35.7% | 100.0% | 47.3% | 55 |
| evoresearcher_blind_n3 | 52 | 22.9% | 35.7% | 100.0% | 34.5% | 55 |
| evoresearcher_blind_n3 | 52 | 28.6% | 50.0% | 100.0% | 41.8% | 55 |
| evoresearcher_blind_n3 | 68 | 0.0% | 0.0% | 50.0% | 3.3% | 60 |
| evoresearcher_blind_n3 | 68 | 0.0% | 0.0% | 25.0% | 1.7% | 60 |
| evoresearcher_blind_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| evoresearcher_n3 | 4 | 18.9% | 27.3% | 100.0% | 29.2% | 72 |
| evoresearcher_n3 | 4 | 9.4% | 0.0% | 100.0% | 18.1% | 72 |
| evoresearcher_n3 | 4 | 5.7% | 36.4% | 100.0% | 20.8% | 72 |
| evoresearcher_n3 | 16 | 18.9% | 83.3% | 100.0% | 38.5% | 52 |
| evoresearcher_n3 | 16 | 24.3% | 0.0% | 100.0% | 23.1% | 52 |
| evoresearcher_n3 | 16 | 18.9% | 83.3% | 100.0% | 38.5% | 52 |
| evoresearcher_n3 | 42 | 8.5% | 23.8% | 100.0% | 21.3% | 75 |
| evoresearcher_n3 | 42 | 8.5% | 28.6% | 85.7% | 21.3% | 75 |
| evoresearcher_n3 | 42 | 4.3% | 4.8% | 85.7% | 12.0% | 75 |
| evoresearcher_n3 | 52 | 25.7% | 21.4% | 100.0% | 32.7% | 55 |
| evoresearcher_n3 | 52 | 8.6% | 7.1% | 100.0% | 18.2% | 55 |
| evoresearcher_n3 | 52 | 28.6% | 35.7% | 100.0% | 38.2% | 55 |
| evoresearcher_n3 | 68 | 0.0% | 0.0% | 50.0% | 3.3% | 60 |
| evoresearcher_n3 | 68 | 2.1% | 0.0% | 75.0% | 6.7% | 60 |
| evoresearcher_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| evoresearcher_noelo_n3 | 4 | 5.7% | 9.1% | 100.0% | 16.7% | 72 |
| evoresearcher_noelo_n3 | 4 | 17.0% | 9.1% | 100.0% | 25.0% | 72 |
| evoresearcher_noelo_n3 | 4 | 11.3% | 27.3% | 100.0% | 23.6% | 72 |
| evoresearcher_noelo_n3 | 16 | 13.5% | 83.3% | 100.0% | 34.6% | 52 |
| evoresearcher_noelo_n3 | 16 | 16.2% | 25.0% | 100.0% | 23.1% | 52 |
| evoresearcher_noelo_n3 | 16 | 27.0% | 91.7% | 100.0% | 46.2% | 52 |
| evoresearcher_noelo_n3 | 42 | 0.0% | 28.6% | 14.3% | 9.3% | 75 |
| evoresearcher_noelo_n3 | 42 | 0.0% | 4.8% | 14.3% | 2.7% | 75 |
| evoresearcher_noelo_n3 | 42 | 0.0% | 28.6% | 57.1% | 13.3% | 75 |
| evoresearcher_noelo_n3 | 52 | 5.7% | 0.0% | 50.0% | 9.1% | 55 |
| evoresearcher_noelo_n3 | 52 | 5.7% | 28.6% | 83.3% | 20.0% | 55 |
| evoresearcher_noelo_n3 | 52 | 31.4% | 50.0% | 100.0% | 43.6% | 55 |
| evoresearcher_noelo_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| evoresearcher_noelo_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| evoresearcher_noelo_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| evoresearcher_warm_n3 | 4 | 1.9% | 18.2% | 37.5% | 8.3% | 72 |
| evoresearcher_warm_n3 | 4 | 18.9% | 63.6% | 100.0% | 34.7% | 72 |
| evoresearcher_warm_n3 | 4 | 17.0% | 18.2% | 100.0% | 26.4% | 72 |
| evoresearcher_warm_n3 | 16 | 13.5% | 33.3% | 100.0% | 23.1% | 52 |
| evoresearcher_warm_n3 | 16 | 18.9% | 0.0% | 100.0% | 19.2% | 52 |
| evoresearcher_warm_n3 | 16 | 18.9% | 91.7% | 100.0% | 40.4% | 52 |
| evoresearcher_warm_n3 | 42 | 12.8% | 19.0% | 85.7% | 21.3% | 75 |
| evoresearcher_warm_n3 | 42 | 4.3% | 28.6% | 85.7% | 18.7% | 75 |
| evoresearcher_warm_n3 | 42 | 2.1% | 38.1% | 85.7% | 20.0% | 75 |
| evoresearcher_warm_n3 | 52 | 31.4% | 50.0% | 100.0% | 43.6% | 55 |
| evoresearcher_warm_n3 | 52 | 40.0% | 42.9% | 100.0% | 47.3% | 55 |
| evoresearcher_warm_n3 | 52 | 17.1% | 28.6% | 50.0% | 23.6% | 55 |
| evoresearcher_warm_n3 | 68 | 0.0% | 0.0% | 25.0% | 1.7% | 60 |
| evoresearcher_warm_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| evoresearcher_warm_n3 | 68 | 0.0% | 0.0% | 75.0% | 5.0% | 60 |
| qwen3_max | 4 | 3.8% | 54.5% | 100.0% | 22.2% | 72 |
| qwen3_max | 16 | 89.2% | 91.7% | 66.7% | 88.5% | 52 |
| qwen3_max | 42 | 34.0% | 23.8% | 85.7% | 36.0% | 75 |
| qwen3_max | 52 | 51.4% | 57.1% | 100.0% | 58.2% | 55 |
| qwen3_max | 68 | 100.0% | 87.5% | 100.0% | 98.3% | 60 |
