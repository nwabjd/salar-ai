# SALAAR NVIDIA NIM Diagnostic Report

Base: `https://integrate.api.nvidia.com/v1`  

Models listed on account: 84  |  Tested: 33  |  Working: 15

## Working models (ranked)

| Rank | Model | Score | Latency | Quality | Streaming |
|------|-------|-------|---------|---------|-----------|
| 1 | poolside/laguna-xs-2.1 | 0.96 | 2.55s | 1.0 | True |
| 2 | nvidia/nemotron-3.5-lightning-30b-a3b | 0.9 | 0.89s | 0.75 | True |
| 3 | nvidia/nemotron-3-nano-omni-30b-a3b-reasoning | 0.76 | 4.39s | 0.5 | True |
| 4 | nvidia/nemotron-3-super-120b-a12b | 0.65 | 0.94s | 0.5 | True |
| 5 | nvidia/nemotron-3-nano-30b-a3b | 0.65 | 0.52s | 0.5 | True |
| 6 | meta/muse-glimmer-30b | 0.65 | 0.44s | 0.5 | True |
| 7 | google/diffusiongemma-26b-a4b-it | 0.65 | 0.99s | 0.5 | True |
| 8 | nvidia/riva-translate-4b-instruct-v2 | 0.65 | 0.51s | 0.5 | True |
| 9 | nvidia/nemotron-3.5-content-safety | 0.65 | 0.46s | 0.5 | True |
| 10 | nvidia/nemotron-3-ultra-550b-a55b | 0.55 | 9.19s | 0.5 | True |
| 11 | nvidia/ising-calibration-1.5-31b | 0.55 | 9.24s | 0.5 | True |
| 12 | deepseek-ai/deepseek-v4-flash-0731 | 0.47 | 86.16s | 0.5 | False |
| 13 | deepseek-ai/deepseek-v4-pro-0813 | 0.335 | 38.09s | 0.25 | True |
| 14 | openai/gpt-oss-20b | 0.2 | Nones | 0.5 | None |
| 15 | moonshotai/kimi-k3 | 0.2 | Nones | 0.5 | None |

## Recommended SALAAR routing (NIM-only)

- **poolside/laguna-xs-2.1** -> overall 0.96, latency 2.55s, quality 1.0, streaming True
- **nvidia/nemotron-3.5-lightning-30b-a3b** -> overall 0.9, latency 0.89s, quality 0.75, streaming True
- **nvidia/nemotron-3-nano-omni-30b-a3b-reasoning** -> overall 0.76, latency 4.39s, quality 0.5, streaming True
- **nvidia/nemotron-3-super-120b-a12b** -> overall 0.65, latency 0.94s, quality 0.5, streaming True
- **nvidia/nemotron-3-nano-30b-a3b** -> overall 0.65, latency 0.52s, quality 0.5, streaming True
- **meta/muse-glimmer-30b** -> overall 0.65, latency 0.44s, quality 0.5, streaming True
- **google/diffusiongemma-26b-a4b-it** -> overall 0.65, latency 0.99s, quality 0.5, streaming True
- **nvidia/riva-translate-4b-instruct-v2** -> overall 0.65, latency 0.51s, quality 0.5, streaming True
- **nvidia/nemotron-3.5-content-safety** -> overall 0.65, latency 0.46s, quality 0.5, streaming True
- **nvidia/nemotron-3-ultra-550b-a55b** -> overall 0.55, latency 9.19s, quality 0.5, streaming True
- **nvidia/ising-calibration-1.5-31b** -> overall 0.55, latency 9.24s, quality 0.5, streaming True
- **deepseek-ai/deepseek-v4-flash-0731** -> overall 0.47, latency 86.16s, quality 0.5, streaming False
- **deepseek-ai/deepseek-v4-pro-0813** -> overall 0.335, latency 38.09s, quality 0.25, streaming True
- **openai/gpt-oss-20b** -> overall 0.2, latency Nones, quality 0.5, streaming None
- **moonshotai/kimi-k3** -> overall 0.2, latency Nones, quality 0.5, streaming None

## Failed / not-provisioned

- google/gemma-4-31b-it: TIMEOUT (http None)
- nvidia/ising-calibration-1-35b-a3b: UNKNOWN (http 410)
- nvidia/cosmos3-nano: ENDPOINT_NOT_SUPPORTED (http 404)
- nvidia/cosmos3-nano-reasoner: ENDPOINT_NOT_SUPPORTED (http 404)
- nvidia/cosmos-transfer2.5-2b: ENDPOINT_NOT_SUPPORTED (http 404)
- stepfun-ai/step-3.7-flash: TIMEOUT (http None)
- nvidia/synthetic-video-detector: ENDPOINT_NOT_SUPPORTED (http 404)
- nvidia/active-speaker-detection: ENDPOINT_NOT_SUPPORTED (http 404)
- nvidia/nemotron-3-embed-1b: NETWORK_ERROR (http None)