import { isAbsolute } from "node:path";

export const STRIP_TOOL_SECRETS_ENV = "PRIME_AGENT_STRIP_TOOL_SECRETS";
export const KERNEL_SANDBOX_COMMAND_ENV = "PRIME_AGENT_KERNEL_SANDBOX_COMMAND";
export const KERNEL_SANDBOX_SETTINGS_ENV = "PRIME_AGENT_KERNEL_SANDBOX_SETTINGS";
export const KERNEL_HOST_REQUEST_ALLOWLIST_ENV = "PRIME_AGENT_KERNEL_HOST_REQUEST_ALLOWLIST";

export interface KernelProcessSpec {
	command: string;
	args: string[];
}

export function childProcessEnv(env: NodeJS.ProcessEnv): NodeJS.ProcessEnv {
	const childEnv = { ...env };
	if (childEnv[STRIP_TOOL_SECRETS_ENV] === "1") {
		delete childEnv.OPENAI_API_KEY;
	}
	return childEnv;
}

export function kernelProcessSpec(python: string, env: NodeJS.ProcessEnv): KernelProcessSpec {
	const command = env[KERNEL_SANDBOX_COMMAND_ENV];
	const settings = env[KERNEL_SANDBOX_SETTINGS_ENV];
	if (command === undefined && settings === undefined) {
		return { command: python, args: ["-m", "rlm.repl"] };
	}
	if (!command || !settings) {
		throw new Error(`${KERNEL_SANDBOX_COMMAND_ENV} and ${KERNEL_SANDBOX_SETTINGS_ENV} must be set together`);
	}
	if (!isAbsolute(command) || !isAbsolute(settings)) {
		throw new Error(`${KERNEL_SANDBOX_COMMAND_ENV} and ${KERNEL_SANDBOX_SETTINGS_ENV} must be absolute paths`);
	}
	return { command, args: ["--settings", settings, python, "-m", "rlm.repl"] };
}

export function kernelHostRequestAllowlist(value: string | undefined): ReadonlySet<string> | undefined {
	if (value === undefined) {
		return undefined;
	}
	return new Set(
		value
			.split(",")
			.map((entry) => entry.trim())
			.filter(Boolean),
	);
}
