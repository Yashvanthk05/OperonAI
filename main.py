import argparse

from agent.config import AgentConfig
from agent.loop import ComputerUseAgent

def main(argv=None):
    parser = argparse.ArgumentParser(description="Operon computer-use agent")
    parser.add_argument("instruction", type=str, nargs="?", default="", help="Natural language instruction for the agent")
    parser.add_argument("--max-iterations", type=int, default=15, help="Maximum agent loop iterations (default: 15)")

    args = parser.parse_args(argv)

    if not args.instruction:
        parser.print_help()
        return 1

    try:
        config = AgentConfig(max_iterations=args.max_iterations)
        agent = ComputerUseAgent(config)
        success, steps = agent.run(args.instruction)

        if success:
            print("Task run finished")
        else:
            print("Stopped after max iterations")
        print(f"Steps executed: {len(steps)}")
        return 0

    except KeyboardInterrupt:
        print("Stopped by user")
        return 0
    except Exception as exc:
        print(f"Run failed: {exc}")
        import traceback
        traceback.print_exc()
        return 1

if __name__ == "__main__":
    main()
