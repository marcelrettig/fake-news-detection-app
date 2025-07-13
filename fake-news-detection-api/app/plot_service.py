import io
import base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from sklearn.metrics import roc_curve, auc, precision_recall_curve

class PlotService:
    def __init__(self, db_client):
        self.db = db_client

    def _load_results(self, benchmark_id: str):
        """Fetch all per‐statement documents for this benchmark."""
        col = self.db.collection("benchmarks").document(benchmark_id).collection("results")
        docs = list(col.stream())
        if not docs:
            raise KeyError(f"No results for benchmark {benchmark_id}")
        # Each doc has 'gold_binary' and 'scores' (a list of floats)
        return [d.to_dict() for d in docs]

    def _make_roc(self, y_true, y_score):
        fpr, tpr, _ = roc_curve(y_true, y_score)
        roc_auc    = auc(fpr, tpr)
        fig, ax = plt.subplots()
        ax.plot(fpr, tpr, label=f"ROC (AUC = {roc_auc:.2f})")
        ax.plot([0,1],[0,1], linestyle="--", label="Chance")
        ax.set_xlabel("False Positive Rate")
        ax.set_ylabel("True Positive Rate")
        ax.set_title("ROC Curve")
        ax.legend(loc="lower right")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def _make_pr(self, y_true, y_score):
        precision, recall, _ = precision_recall_curve(y_true, y_score)
        pr_auc               = auc(recall, precision)
        fig, ax = plt.subplots()
        ax.plot(recall, precision, label=f"PR (AUC = {pr_auc:.2f})")
        ax.set_xlabel("Recall")
        ax.set_ylabel("Precision")
        ax.set_title("Precision–Recall Curve")
        ax.legend(loc="lower left")
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight")
        plt.close(fig)
        buf.seek(0)
        return buf

    def generate_plots(self, benchmark_id: str):
        results = self._load_results(benchmark_id)
        # flatten: take first score from each row
        y_true  = [int(r["gold_binary"]) for r in results]
        y_score = [r["scores"][0] if r["scores"] else 0.0 for r in results]

        roc_buf = self._make_roc(y_true, y_score)
        pr_buf  = self._make_pr(y_true, y_score)

        # return base64 strings so UI can render <img src="data:image/png;base64,..." />
        return {
            "roc_curve":        base64.b64encode(roc_buf.getvalue()).decode("ascii"),
            "pr_auc_curve":     base64.b64encode(pr_buf.getvalue()).decode("ascii"),
        }
