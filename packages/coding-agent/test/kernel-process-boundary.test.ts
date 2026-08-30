import { chmodSync, mkdtempSync, readFileSync, rmSync, writeFileSync } from "node:fs";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { afterEach, describe, expect, it, vi } from "vitest";
import { ReplKernelManager } from "../src/core/kernel/index.js";
import {
	childProcessEnv,
	KERNEL_HOST_REQUEST_ALLOWLIST_ENV,
	KERNEL_SANDBOX_COMMAND_ENV,
	KERNEL_SANDBOX_SETTINGS_ENV,
	kernelHostRequestAllowlist,
	kernelProcessSpec,
	STRIP_TOOL_SECRETS_ENV,
} from "../src/core/kernel/process-boundary.js";

const savedEnv = { ...process.env };
let tempDir = "";

afterEach(() => {
	for (const key of Object.keys(process.env)) {
		if (!(key in savedEnv)) delete process.env[key];
	}
	Object.assign(process.env, savedEnv);
	if (tempDir) {
		rmSync(tempDir, { recursive: true, force: true });
		tempDir = "";
	}
});

describe("kernel process boundary", () => {
	it("keeps default child behavior and strips only the opted-in tool secret", () => {
		expect(childProcessEnv({ OPENAI_API_KEY: "secret" }).OPENAI_API_KEY).toBe("secret");
		expect(childProcessEnv({ OPENAI_API_KEY: "secret", [STRIP_TOOL_SECRETS_ENV]: "1", PATH: "/bin" })).toEqual({
			[STRIP_TOOL_SECRETS_ENV]: "1",
			PATH: "/bin",
		});
	});

	it("requires an absolute sandbox wrapper pair", () => {
		expect(kernelProcessSpec("/venv/bin/python", {})).toEqual({
			command: "/venv/bin/python",
			args: ["-m", "rlm.repl"],
		});
		expect(
			kernelProcessSpec("/venv/bin/python", {
				[KERNEL_SANDBOX_COMMAND_ENV]: "/usr/local/bin/kernel-sandbox",
				[KERNEL_SANDBOX_SETTINGS_ENV]: "/private/kernel.settings",
			}),
		).toEqual({
			command: "/usr/local/bin/kernel-sandbox",
			args: ["--settings", "/private/kernel.settings", "/venv/bin/python", "-m", "rlm.repl"],
		});
		expect(() => kernelProcessSpec("/venv/bin/python", { [KERNEL_SANDBOX_COMMAND_ENV]: "/usr/bin/sandbox" })).toThrow(
			/must be set together/,
		);
		expect(() =>
			kernelProcessSpec("/venv/bin/python", {
				[KERNEL_SANDBOX_COMMAND_ENV]: "sandbox",
				[KERNEL_SANDBOX_SETTINGS_ENV]: "/private/kernel.settings",
			}),
		).toThrow(/must be absolute paths/);
	});

	it("parses an exact comma-separated host request allowlist", () => {
		expect(kernelHostRequestAllowlist(undefined)).toBeUndefined();
		expect([...kernelHostRequestAllowlist(" rlm.run, goal.get ,,rlm.run ")!]).toEqual(["rlm.run", "goal.get"]);
		expect(kernelHostRequestAllowlist("")?.size).toBe(0);
	});

	it("rejects a host request before dispatch when it is not allowlisted", async () => {
		const allowed = vi.fn(async () => ({ ok: true }));
		const blocked = vi.fn(async () => ({ ok: true }));
		const manager = new ReplKernelManager({
			env: { [KERNEL_HOST_REQUEST_ALLOWLIST_ENV]: "test.allowed" },
			hostHandlers: { "test.allowed": allowed, "test.blocked": blocked },
		});
		const handleHostRequest = (
			manager as unknown as { handleHostRequest(data: unknown): Promise<Record<string, unknown>> }
		).handleHostRequest.bind(manager);

		await expect(handleHostRequest({ type: "test.blocked" })).rejects.toThrow(/is not allowed/);
		expect(blocked).not.toHaveBeenCalled();
		await expect(handleHostRequest({ type: "test.allowed" })).resolves.toEqual({ ok: true });
		expect(allowed).toHaveBeenCalledOnce();
	});

	it("runs the kernel through the configured wrapper without leaking the OpenAI key", async () => {
		tempDir = mkdtempSync(join(tmpdir(), "prime-agent-kernel-boundary-"));
		const argsDump = join(tempDir, "args");
		const envDump = join(tempDir, "env");
		const settings = join(tempDir, "settings");
		const python = join(tempDir, "python");
		const wrapper = join(tempDir, "wrapper");
		writeFileSync(settings, "settings\n");
		writeFileSync(python, `#!/bin/sh\nenv > ${JSON.stringify(envDump)}\nexit 42\n`);
		writeFileSync(wrapper, `#!/bin/sh\nprintf '%s\\n' "$@" > ${JSON.stringify(argsDump)}\nexec "$3" "$4" "$5"\n`);
		chmodSync(python, 0o755);
		chmodSync(wrapper, 0o755);
		process.env.OPENAI_API_KEY = "must-not-leak";
		process.env[STRIP_TOOL_SECRETS_ENV] = "1";
		process.env[KERNEL_SANDBOX_COMMAND_ENV] = wrapper;
		process.env[KERNEL_SANDBOX_SETTINGS_ENV] = settings;
		const manager = new ReplKernelManager({ python, cwd: tempDir });

		try {
			await expect(manager.execute("x")).rejects.toThrow(/Kernel exited before ready/);
		} finally {
			await manager.shutdown({ snapshot: true, drainHostRequests: true });
		}

		expect(readFileSync(argsDump, "utf8").trim().split("\n")).toEqual([
			"--settings",
			settings,
			python,
			"-m",
			"rlm.repl",
		]);
		expect(readFileSync(envDump, "utf8")).not.toContain("OPENAI_API_KEY=");
	});
});
