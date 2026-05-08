export class ApiError extends Error {
  constructor(
    public readonly status: number,
    public readonly detail: string,
    public readonly url: string,
  ) {
    super(`API ${status} at ${url}: ${detail}`);
    this.name = "ApiError";
  }
}

export class NetworkError extends Error {
  constructor(
    public readonly cause: unknown,
    public readonly url: string,
  ) {
    super(`Network error at ${url}: ${String(cause)}`);
    this.name = "NetworkError";
  }
}
