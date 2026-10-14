"""pm4py and Pandas Process Mining analyzer for bottleneck and ping-pong loop detection."""
import logging
from typing import Dict, Any, List, Tuple, Optional
import pandas as pd

logger = logging.getLogger("process_mining.analyzer")

try:
    import pm4py
    PM4PY_AVAILABLE = True
except ImportError:
    PM4PY_AVAILABLE = False


class ProcessMiningAnalyzer:
    """Analyzes ITSM event logs using pm4py and pandas to uncover operational inefficiencies."""

    def __init__(self, df: pd.DataFrame):
        self.df = df.copy()
        if not self.df.empty and "time:timestamp" in self.df.columns:
            self.df["time:timestamp"] = pd.to_datetime(self.df["time:timestamp"])

    def get_summary_statistics(self) -> Dict[str, Any]:
        """Compute basic process metrics."""
        if self.df.empty:
            return {"total_events": 0, "total_cases": 0, "activities": []}

        cases = self.df["case:concept:name"].nunique()
        events = len(self.df)
        activities = self.df["concept:name"].unique().tolist()

        return {
            "total_events": events,
            "total_cases": cases,
            "activities": activities,
            "events_per_case_avg": round(events / max(1, cases), 2),
        }

    def detect_bottlenecks(self) -> List[Dict[str, Any]]:
        """Calculate transition dwell times between successive activities to surface bottlenecks."""
        if self.df.empty or len(self.df) < 2:
            return []

        df_sorted = self.df.sort_values(by=["case:concept:name", "time:timestamp"]).copy()
        df_sorted["next_activity"] = df_sorted.groupby("case:concept:name")["concept:name"].shift(-1)
        df_sorted["next_time"] = df_sorted.groupby("case:concept:name")["time:timestamp"].shift(-1)

        valid_transitions = df_sorted.dropna(subset=["next_activity", "next_time"]).copy()
        valid_transitions["duration_hours"] = (
            valid_transitions["next_time"] - valid_transitions["time:timestamp"]
        ).dt.total_seconds() / 3600.0

        bottlenecks = []
        grouped = valid_transitions.groupby(["concept:name", "next_activity"])

        for (act_from, act_to), group in grouped:
            count = len(group)
            mean_hrs = group["duration_hours"].mean()
            median_hrs = group["duration_hours"].median()
            max_hrs = group["duration_hours"].max()

            bottlenecks.append({
                "from_activity": act_from,
                "to_activity": act_to,
                "transition_count": count,
                "mean_duration_hours": round(mean_hrs, 2),
                "median_duration_hours": round(median_hrs, 2),
                "max_duration_hours": round(max_hrs, 2),
            })

        # Sort descending by mean duration
        bottlenecks.sort(key=lambda x: x["mean_duration_hours"], reverse=True)
        return bottlenecks

    def detect_ping_pong_loops(self) -> Dict[str, Any]:
        """Detect tickets bouncing repeatedly between assignment groups."""
        if self.df.empty:
            return {"ping_pong_cases": 0, "ping_pong_rate_pct": 0.0, "top_bouncing_pairs": []}

        reassigned_df = self.df[self.df["concept:name"] == "Reassigned"].copy()
        if reassigned_df.empty:
            return {"ping_pong_cases": 0, "ping_pong_rate_pct": 0.0, "top_bouncing_pairs": []}

        reassign_counts = reassigned_df.groupby("case:concept:name").size()
        ping_pong_cases = reassign_counts[reassign_counts >= 2].index.tolist()

        total_cases = self.df["case:concept:name"].nunique()
        rate_pct = round((len(ping_pong_cases) / max(1, total_cases)) * 100, 2)

        # Find bouncing team transitions
        reassigned_df["prev_group"] = reassigned_df.groupby("case:concept:name")["org:group"].shift(1)
        bounces = reassigned_df.dropna(subset=["prev_group"])
        pair_counts = bounces.groupby(["prev_group", "org:group"]).size().reset_index(name="count")
        pair_counts = pair_counts.sort_values(by="count", ascending=False)

        top_pairs = []
        for _, row in pair_counts.head(5).iterrows():
            top_pairs.append({
                "from_group": row["prev_group"],
                "to_group": row["org:group"],
                "bounce_count": int(row["count"]),
            })

        return {
            "ping_pong_cases_count": len(ping_pong_cases),
            "total_cases_evaluated": total_cases,
            "ping_pong_rate_pct": rate_pct,
            "top_bouncing_pairs": top_pairs,
        }

    def compute_dfg(self) -> Dict[str, Any]:
        """Compute Directly-Follows Graph frequency matrix using pm4py if available, or pandas."""
        if PM4PY_AVAILABLE and not self.df.empty:
            try:
                dfg, start_acts, end_acts = pm4py.discover_dfg(self.df)
                formatted_dfg = [
                    {"source": k[0], "target": k[1], "count": v} for k, v in dfg.items()
                ]
                return {
                    "dfg": formatted_dfg,
                    "start_activities": list(start_acts.keys()),
                    "end_activities": list(end_acts.keys()),
                }
            except Exception as e:
                logger.warning(f"pm4py DFG discovery fallback: {e}")

        # Fallback DFG calculation with Pandas
        df_sorted = self.df.sort_values(by=["case:concept:name", "time:timestamp"]).copy()
        df_sorted["next_activity"] = df_sorted.groupby("case:concept:name")["concept:name"].shift(-1)
        valid = df_sorted.dropna(subset=["next_activity"])
        transitions = valid.groupby(["concept:name", "next_activity"]).size().reset_index(name="count")

        return {
            "dfg": [
                {"source": r["concept:name"], "target": r["next_activity"], "count": int(r["count"])}
                for _, r in transitions.iterrows()
            ],
            "start_activities": ["Created"],
            "end_activities": ["Resolved"],
        }
