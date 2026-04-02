import { readFile } from "node:fs/promises"
import path from "node:path"

export interface ServerConfig {
  host: string
  port: number
  dataDir: string
  certFile: string
  keyFile: string
  keyPassword?: string
}

const requiredDataFiles = [
  "COMPOUND_CID_4.json",
  "Structure2D_COMPOUND_CID_4.json",
  "Conformer3D_COMPOUND_CID_4(1).json",
] as const

async function pathExists(filePath: string): Promise<boolean> {
  try {
    await readFile(filePath)
    return true
  } catch {
    return false
  }
}

function firstEnvValue(...names: readonly string[]): string | undefined {
  for (const name of names) {
    const value = process.env[name]
    if (value) {
      return value
    }
  }

  return undefined
}

function firstIntEnvValue(...names: readonly string[]): number | undefined {
  for (const name of names) {
    const value = process.env[name]
    if (!value) {
      continue
    }

    const parsed = Number.parseInt(value, 10)
    if (Number.isInteger(parsed) && parsed > 0 && parsed <= 65535) {
      return parsed
    }
  }

  return undefined
}

export async function resolveDataDir(): Promise<string> {
  const candidates: string[] = []
  if (process.env.DATA_DIR) {
    candidates.push(path.resolve(process.env.DATA_DIR))
  }

  const repoDataDir = path.resolve(import.meta.dirname, "../../data")
  candidates.push(repoDataDir, path.resolve(process.cwd(), "data"), path.resolve(process.cwd(), "../data"))

  for (const candidate of candidates) {
    const hasAllRequiredFiles = await Promise.all(
      requiredDataFiles.map((fileName) => pathExists(path.join(candidate, fileName))),
    )

    if (hasAllRequiredFiles.every(Boolean)) {
      return candidate
    }
  }

  throw new Error(`Unable to resolve the CID 4 data directory. Checked: ${candidates.join(", ")}`)
}

export async function resolveServerConfig(dataDir: string): Promise<ServerConfig> {
  const host = firstEnvValue("NEST_HOST", "NESTJS_HOST", "SERVER_HOST") ?? "0.0.0.0"
  const port = firstIntEnvValue("NEST_PORT", "NESTJS_PORT", "SERVER_PORT", "PORT") ?? 8443

  const certFile = firstEnvValue("TLS_CERT_FILE")
  const keyFile = firstEnvValue("TLS_KEY_FILE")
  const keyPassword = firstEnvValue("TLS_KEY_PASSWORD")

  const config = certFile || keyFile
    ? resolveExplicitTlsConfig({ host, port, dataDir, certFile, keyFile, keyPassword })
    : await resolveServerConfigFromCryptoSummary(dataDir, host, port)

  if (!(await pathExists(config.certFile))) {
    throw new Error(`TLS certificate file does not exist: ${config.certFile}`)
  }

  if (!(await pathExists(config.keyFile))) {
    throw new Error(`TLS private key file does not exist: ${config.keyFile}`)
  }

  return config
}

function resolveExplicitTlsConfig(input: {
  host: string
  port: number
  dataDir: string
  certFile?: string
  keyFile?: string
  keyPassword?: string
}): ServerConfig {
  if (!input.certFile || !input.keyFile) {
    throw new Error(
      "Set both TLS_CERT_FILE and TLS_KEY_FILE, or neither to use the crypto summary fallback.",
    )
  }

  return {
    host: input.host,
    port: input.port,
    dataDir: input.dataDir,
    certFile: path.resolve(input.certFile),
    keyFile: path.resolve(input.keyFile),
    keyPassword: input.keyPassword,
  }
}

async function resolveServerConfigFromCryptoSummary(
  dataDir: string,
  host: string,
  port: number,
): Promise<ServerConfig> {
  const summaryPath = path.join(dataDir, "out", "crypto", "cid4_crypto.summary.json")
  if (!(await pathExists(summaryPath))) {
    throw new Error(
      `No TLS certificate configuration found. Set TLS_CERT_FILE and TLS_KEY_FILE, or generate ${summaryPath} first.`,
    )
  }

  const summary = JSON.parse(await readFile(summaryPath, "utf-8")) as {
    demo_password?: string
    x509_and_pkcs12?: {
      pem_paths?: {
        certificate?: string
        private_key?: string
      }
    }
  }

  const certPath = summary.x509_and_pkcs12?.pem_paths?.certificate
  const keyPath = summary.x509_and_pkcs12?.pem_paths?.private_key

  if (!certPath || !keyPath) {
    throw new Error(`NestJS TLS fallback requires PEM paths in ${summaryPath}`)
  }

  return {
    host,
    port,
    dataDir,
    certFile: path.resolve(certPath),
    keyFile: path.resolve(keyPath),
    keyPassword: summary.demo_password,
  }
}

export function isSupportedConformerIndex(index: number): boolean {
  return index >= 1 && index <= 6
}

export function conformerPath(dataDir: string, index: number): string {
  if (!isSupportedConformerIndex(index)) {
    throw new RangeError(`Unknown conformer ${index}`)
  }

  return path.join(dataDir, `Conformer3D_COMPOUND_CID_4(${index}).json`)
}

export function structure2dPath(dataDir: string): string {
  return path.join(dataDir, "Structure2D_COMPOUND_CID_4.json")
}

export function compoundPath(dataDir: string): string {
  return path.join(dataDir, "COMPOUND_CID_4.json")
}

export async function loadJsonDocument<T>(filePath: string): Promise<T> {
  return JSON.parse(await readFile(filePath, "utf-8")) as T
}

export function isoTimestampUtc(): string {
  return new Date().toISOString()
}
