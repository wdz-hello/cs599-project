"""DevMind CLI — command-line entry point for the multi-agent system."""

import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.agents.orchestrator import run_workflow
from src.config.settings import settings


def main():
    print("=" * 60)
    print("🧠 DevMind — SDD 驱动的多智能体软件开发助手")
    print("=" * 60)

    # Validate config
    try:
        settings.validate()
    except ValueError as e:
        print(f"\n❌ 配置错误: {e}")
        print("请复制 .env.example 为 .env 并填入 DeepSeek API Key")
        sys.exit(1)

    print(f"\n📡 LLM: {settings.DEEPSEEK_MODEL}")
    print(f"🔗 API: {settings.DEEPSEEK_BASE_URL}")

    # Get user input
    print("\n" + "-" * 40)
    print("请描述你想要开发的软件需求（输入 END 结束）：")
    print("-" * 40)

    lines = []
    while True:
        try:
            line = input()
            if line.strip().upper() == "END":
                break
            lines.append(line)
        except EOFError:
            break

    requirement = "\n".join(lines).strip()
    if not requirement:
        print("❌ 需求不能为空，程序退出。")
        sys.exit(1)

    print("\n🚀 开始执行 DevMind 工作流...\n")

    # Run the workflow
    result = run_workflow(requirement=requirement)

    # Print results
    phase = result.get("phase", "unknown")
    print(f"\n📊 工作流状态: {phase}")

    review = result.get("review_result")
    if review:
        print(f"\n📋 代码审查: {review.get('score', 'N/A')}/100 — {'✅ 通过' if review.get('passed') else '❌ 未通过'}")

    test_result = result.get("test_result")
    if test_result:
        print(f"🧪 测试结果: {test_result.get('passed', 0)}/{test_result.get('total', 0)} 通过")

    files = result.get("generated_files", [])
    if files:
        print(f"\n📁 生成的文件 ({len(files)}):")
        for f in files:
            print(f"  - {f.get('path', 'unknown')} ({f.get('action', 'create')})")

    final_report = result.get("final_report")
    if final_report:
        print("\n" + "=" * 60)
        print(final_report)

    print("\n✅ DevMind 工作流执行完毕。")


if __name__ == "__main__":
    main()
