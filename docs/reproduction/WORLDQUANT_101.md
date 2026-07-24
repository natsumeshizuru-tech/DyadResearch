# 101 Formulaic Alphas

The source ledger contains 101/101 Appendix A formula records. The paper's
realized return, volatility, turnover and covariance inputs are proprietary.
Accordingly:

- operator and formula work can be tested independently;
- equivalent US-market numerical reproduction is `NOT_RUN` locally;
- A-share work is called formula reproduction plus transfer testing;
- Alphas 42, 48, 53 and 54 retain their delay-0 label and require separate
  close-time and safe t+1-open interpretation.

`adv{d}` means average daily dollar turnover. It is not average share volume.
VWAP requires explicit amount/volume unit conversion.

```text
dyadresearch reproduce audit worldquant101
dyadresearch reproduce run worldquant101 --protocol formula-validation
dyadresearch reproduce run worldquant101 --protocol original-market
```

The current implementation coverage is shown by generated protocol and
acceptance reports; this page deliberately does not freeze a potentially stale
count.

