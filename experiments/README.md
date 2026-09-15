# Evaluation harness

Run from the project root:

```powershell
.\.venv\Scripts\python.exe experiments\evaluate_methods.py
```

To preserve a private result artifact:

```powershell
.\.venv\Scripts\python.exe experiments\evaluate_methods.py --output experiments\results\latest.json
```

The runner compares a keyword baseline with the hybrid extraction pipeline on the repository dataset and deterministic paraphrase stress tests. These results are engineering checks. A conference paper still needs an independently collected, held-out, annotated corpus; pre-registered metrics; statistical confidence intervals; and ablation studies.
