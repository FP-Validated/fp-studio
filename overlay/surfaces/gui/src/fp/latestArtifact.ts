/** Request ordering only. No UI, layout, CSS or rendering implementation. */
export class LatestArtifactReader<T> {
  private epoch = 0;
  constructor(private fetcher: (session: string, path: string) => Promise<T>) {}
  invalidate(): void { this.epoch += 1; }
  async read(session: string, path: string, commit: (value: T) => void): Promise<void> {
    const epoch = ++this.epoch;
    try {
      const value = await this.fetcher(session, path);
      if (this.epoch === epoch) commit(value);
    } catch {
      // Keep the last successfully displayed artifact on a transient reload error.
      // A different session/path is cleared by the existing viewer before it calls us.
    }
  }
}
