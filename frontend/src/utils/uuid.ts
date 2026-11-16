/** RFC 4122 v4 disponible también en HTTP LAN sin contexto seguro. */
export function safeRandomUUID(): string {
  const cryptoProvider = globalThis.crypto;
  if (
    globalThis.isSecureContext &&
    typeof cryptoProvider?.randomUUID === "function"
  ) {
    return cryptoProvider.randomUUID();
  }
  if (!cryptoProvider?.getRandomValues)
    throw new Error(
      "Este navegador no dispone de un generador seguro de identificadores.",
    );
  const bytes = cryptoProvider.getRandomValues(new Uint8Array(16));
  bytes[6] = (bytes[6] & 0x0f) | 0x40;
  bytes[8] = (bytes[8] & 0x3f) | 0x80;
  const hex = Array.from(bytes, (value) =>
    value.toString(16).padStart(2, "0"),
  ).join("");
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`;
}
