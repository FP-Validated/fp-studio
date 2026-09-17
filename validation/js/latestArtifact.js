"use strict";
Object.defineProperty(exports, "__esModule", { value: true });
exports.LatestArtifactReader = void 0;
/** Request ordering only. No UI, layout, CSS or rendering implementation. */
class LatestArtifactReader {
    fetcher;
    epoch = 0;
    constructor(fetcher) {
        this.fetcher = fetcher;
    }
    invalidate() { this.epoch += 1; }
    async read(session, path, commit) {
        const epoch = ++this.epoch;
        try {
            const value = await this.fetcher(session, path);
            if (this.epoch === epoch)
                commit(value);
        }
        catch {
            // Keep the last successfully displayed artifact on a transient reload error.
            // A different session/path is cleared by the existing viewer before it calls us.
        }
    }
}
exports.LatestArtifactReader = LatestArtifactReader;
