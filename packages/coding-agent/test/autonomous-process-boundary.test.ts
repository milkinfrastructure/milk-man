import { execFileSync } from "node:child_process";
import { mkdtempSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fauxAssistantMessage } from "@earendil-works/pi-ai";
import { afterEach, describe, expect, it } from "vitest";
import { createAutonomousRuntimeState, nextAutonomousContinuation } from "../src/core/autonomous.js";
import { STRIP_TOOL_SECRETS_ENV } from "../src/core/kernel/process-boundary.js";

const originalOpenAiKey = process.env.OPENAI_API_KEY;
const originalStripFlag = process.env[STRIP_TOOL_SECRETS_ENV];
let tempDir = "";

afterEach(() => {
	if (originalOpenAiKey === undefined) delete process.env.OPENAI_API_KEY;
	else process.env.OPENAI_API_KEY = originalOpenAiKey;
	if (originalStripFlag === undefined) delete process.env[STRIP_TOOL_SECRETS_ENV];
	else process.env[STRIP_TOOL_SECRETS_ENV] = originalStripFlag;
	if (tempDir) {
		rmSync(tempDir, { recursive: true, force: true });
		tempDir = "";
	}
});

describe("autonomous process boundary", () => {
	it("strips the OpenAI key from autonomous gate children when opted in", async () => {
		tempDir = mkdtempSync(join(tmpdir(), "prime-agent-autonomous-boundary-"));
		execFileSync("git", ["init"], { cwd: tempDir, stdio: "ignore" });
		execFileSync("git", ["config", "user.email", "test@example.com"], { cwd: tempDir });
		execFileSync("git", ["config", "user.name", "Test User"], { cwd: tempDir });
		writeFileSync(join(tempDir, "tracked"), "initial\n");
		execFileSync("git", ["add", "tracked"], { cwd: tempDir });
		execFileSync("git", ["-c", "commit.gpgsign=false", "commit", "--no-gpg-sign", "-m", "initial"], {
			cwd: tempDir,
			stdio: "ignore",
		});
		process.env.OPENAI_API_KEY = "must-not-leak";
		process.env[STRIP_TOOL_SECRETS_ENV] = "1";
		const gate = `${process.execPath} -e "process.exit(process.env.OPENAI_API_KEY === undefined ? 0 : 9)"`;
		const state = createAutonomousRuntimeState({
			enabled: true,
			gates: { commands: [gate], maxRetries: 1 },
		});

		const continuation = await nextAutonomousContinuation(state, fauxAssistantMessage("Done."), { cwd: tempDir });

		expect(continuation).toBeUndefined();
		expect(state.lastGateFailure).toBeUndefined();
	});
});
