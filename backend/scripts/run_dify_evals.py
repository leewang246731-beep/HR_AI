
from __future__ import annotations

import argparse
import asyncio
import shutil
import sys
from datetime import datetime
from pathlib import Path

"""运行 Dify 工作流固定评估集。"""

BACKEND_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND_DIR))

from app.evaluations.dify_eval_runner import (
    DifyEvalRunner,
    load_eval_cases,
    write_json_report,
    write_markdown_report,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="运行 Dify 工作流评估。",
        add_help=False,
        usage="python scripts/run_dify_evals.py [选项]",
    )
    parser._optionals.title = "选项"
    parser.add_argument("-h", "--help", action="help", help="显示帮助信息并退出。")
    parser.add_argument(
        "--cases",
        type=Path,
        metavar="样例路径",
        default=BACKEND_DIR / "evals" / "dify_cases",
        help="JSON 评估样例文件路径，或包含多个 JSON 评估样例文件的目录。",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        metavar="报告目录",
        default=BACKEND_DIR / "evals" / "reports",
        help="JSON 和 Markdown 评估报告的输出目录。",
    )
    parser.add_argument("--repeat-runs", type=int, default=3, metavar="次数", help="每条样例重复运行次数。")
    parser.add_argument("--concurrency", type=int, default=1, metavar="数量", help="并发执行的样例数量。")
    parser.add_argument("--llm-judge", action="store_true", help="启用大模型裁判评分。")
    parser.add_argument("--stream", action="store_true", help="使用 Dify 流式接口；默认使用阻塞接口。")
    parser.add_argument("--baseline", type=Path, default=None, metavar="基线报告", help="用于回归对比的历史 JSON 报告路径。")
    parser.add_argument("--fail-on-regression", action="store_true", help="如果通过率或分数回退，则以非零状态码退出。")
    parser.add_argument("--fail-on-failed-cases", action="store_true", help="如果存在失败样例，则以非零状态码退出。")
    return parser.parse_args()


async def main() -> int:
    args = parse_args()
    cases_path = args.cases if args.cases.is_absolute() else BACKEND_DIR / args.cases
    output_dir = args.output_dir if args.output_dir.is_absolute() else BACKEND_DIR / args.output_dir
    baseline_path = None
    if args.baseline:
        baseline_path = args.baseline if args.baseline.is_absolute() else BACKEND_DIR / args.baseline

    cases = load_eval_cases(cases_path)
    if not cases:
        print(f"未读取到评估样例: {cases_path}")
        return 2

    print(f"读取评估样例: {len(cases)} 条")
    print(f"重复运行次数: {args.repeat_runs}")
    print(f"大模型裁判: {'启用' if args.llm_judge else '关闭'}")
    print(f"Dify 调用模式: {'流式' if args.stream else '阻塞'}")

    runner = DifyEvalRunner()
    report = await runner.run(
        cases=cases,
        repeat_runs=args.repeat_runs,
        use_llm_judge=args.llm_judge,
        use_stream=args.stream,
        concurrency=args.concurrency,
        baseline_path=baseline_path,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    json_path = output_dir / f"dify_eval_{timestamp}.json"
    md_path = output_dir / f"dify_eval_{timestamp}.md"
    latest_json_path = output_dir / "dify_eval_latest.json"
    latest_md_path = output_dir / "dify_eval_latest.md"
    write_json_report(report, json_path)
    write_markdown_report(report, md_path)
    shutil.copyfile(json_path, latest_json_path)
    shutil.copyfile(md_path, latest_md_path)

    print("")
    print("=== Dify 评估完成 ===")
    print(f"总样例: {report.total_cases}")
    print(f"通过: {report.passed_cases}")
    print(f"失败: {report.failed_cases}")
    print(f"通过率: {report.pass_rate:.2%}")
    print(f"规则平均分: {report.average_rule_score:.4f}")
    if report.average_judge_score is not None:
        print(f"大模型裁判平均分: {report.average_judge_score:.4f}")
    print(f"平均延迟: {report.average_latency_ms:.2f} ms")
    if report.regression:
        print("")
        print("=== 回归对比 ===")
        print(f"基线: {report.regression.baseline_path}")
        print(f"通过率变化: {report.regression.pass_rate_delta}")
        print(f"规则分变化: {report.regression.average_score_delta}")
    print("")
    print(f"JSON 报告: {json_path}")
    print(f"Markdown 报告: {md_path}")

    if args.fail_on_failed_cases and report.failed_cases:
        return 1
    if args.fail_on_regression and report.regression:
        pass_rate_delta = report.regression.pass_rate_delta or 0
        score_delta = report.regression.average_score_delta or 0
        if pass_rate_delta < 0 or score_delta < 0:
            return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))
