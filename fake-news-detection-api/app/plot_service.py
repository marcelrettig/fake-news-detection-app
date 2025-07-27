import io
import base64
import logging

import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, precision_recall_curve

logger = logging.getLogger(__name__)

class PlotService:
    def __init__(self, db_client):
        self.db = db_client

    def _load_results(self, benchmark_id: str):
        col = (
            self.db.collection("benchmarks")
                   .document(benchmark_id)
                   .collection("results")
        )
        docs = list(col.stream())
        if not docs:
            raise KeyError(f"No results for benchmark {benchmark_id}")
        return [d.to_dict() for d in docs]

    def _make_roc(self, y_true, y_score):
        # Compute ROC treating 'Fake' as the positive class
        fpr, tpr, roc_thresholds = roc_curve(y_true, y_score)
        roc_auc = auc(fpr, tpr)

        logger.info(f"[{roc_thresholds.size} ROC points] thresholds: {roc_thresholds}")
        print(f"[{roc_thresholds.size} ROC points] thresholds: {roc_thresholds}")

        fig, ax = plt.subplots()
        ax.plot(fpr, tpr, label=f"ROC (AUC = {roc_auc:.2f})")
        ax.plot([0,1], [0,1], linestyle="--", label="Chance")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("ROC Curve (Fake as Positive)")
        ax.legend(loc="lower right")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_pr(self, y_true, y_score):
        # Compute PR treating 'Fake' as the positive class
        precision, recall, pr_thresholds = precision_recall_curve(y_true, y_score)
        pr_auc = auc(recall, precision)

        logger.info(f"[{pr_thresholds.size} PR points] thresholds: {pr_thresholds}")
        print(f"[{pr_thresholds.size} PR points] thresholds: {pr_thresholds}")

        fig, ax = plt.subplots()
        ax.plot(recall, precision, label=f"PR (AUC = {pr_auc:.2f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title("Precision–Recall Curve (Fake as Positive)")
        ax.legend(loc="lower left")

        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_plots(self, benchmark_id: str):
        # Load all results for this benchmark
        results = self._load_results(benchmark_id)

        # Flatten true labels and scores
        y_true  = [int(r["gold_binary"]) for r in results for _ in r["scores"]]
        y_score = [float(s)            for r in results for s in r["scores"]]

        # Invert labels and scores so that 'Fake' (gold_binary == 0) is positive
        y_true  = [1 - y for y in y_true]
        y_score = [1 - s for s in y_score]

        logger.info(f"Benchmark {benchmark_id}: using {len(y_score)} total scores")
        logger.info(f"Score values (inverted): {y_score}")
        print(f"Benchmark {benchmark_id}: using {len(y_score)} total scores")
        print(f"Score values (inverted): {y_score}")

        # Generate individual plots
        roc_buf = self._make_roc(y_true, y_score)
        pr_buf  = self._make_pr(y_true, y_score)

        # Return base64‐encoded images
        return {
            "roc_curve":    base64.b64encode(roc_buf.getvalue()).decode("ascii"),
            "pr_auc_curve": base64.b64encode(pr_buf.getvalue()).decode("ascii"),
        }

    def generate_comparison_plots(self, benchmark_ids: list[str]):
        """
        Loads each benchmark’s results, computes ROC & PR,
        and returns two base64-encoded PNGs with all curves overlaid,
        treating 'Fake' as positive.
        """
        roc_data = {}
        pr_data  = {}

        for bid in benchmark_ids:
            results = self._load_results(bid)
            y_true  = [int(r["gold_binary"]) for r in results]
            y_score = [r["scores"][0] if r["scores"] else 0.0 for r in results]

            # Invert for 'Fake' as positive
            y_true  = [1 - y for y in y_true]
            y_score = [1 - s for s in y_score]

            # Compute curves
            fpr, tpr, _          = roc_curve(y_true, y_score)
            precision, recall, _ = precision_recall_curve(y_true, y_score)

            roc_data[bid] = (fpr, tpr, auc(fpr, tpr))
            pr_data[bid]  = (recall, precision, auc(recall, precision))

        # Plot ROC comparison
        fig1, ax1 = plt.subplots()
        for bid, (fpr, tpr, roc_auc) in roc_data.items():
            ax1.plot(fpr, tpr, label=f"{bid} (AUC={roc_auc:.2f})")
        ax1.plot([0,1], [0,1], linestyle="--", color="gray", label="Chance")
        ax1.set_xlabel("False Positive Rate")
        ax1.set_ylabel("True Positive Rate")
        ax1.set_title("ROC Curve Comparison (Fake as Positive)")
        ax1.legend(loc="lower right")
        buf1 = io.BytesIO()
        fig1.savefig(buf1, format="png", bbox_inches="tight")
        plt.close(fig1)
        buf1.seek(0)

        # Plot PR comparison
        fig2, ax2 = plt.subplots()
        for bid, (recall, precision, pr_auc) in pr_data.items():
            ax2.plot(recall, precision, label=f"{bid} (AUC={pr_auc:.2f})")
        ax2.set_xlabel("Recall")
        ax2.set_ylabel("Precision")
        ax2.set_title("Precision–Recall Curve Comparison (Fake as Positive)")
        ax2.legend(loc="lower left")
        buf2 = io.BytesIO()
        fig2.savefig(buf2, format="png", bbox_inches="tight")
        plt.close(fig2)
        buf2.seek(0)

        return {
            "roc_comparison": base64.b64encode(buf1.getvalue()).decode("ascii"),
            "pr_comparison":  base64.b64encode(buf2.getvalue()).decode("ascii"),
        }
