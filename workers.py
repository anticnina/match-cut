"""QRunnable workers for background scraping/analysis."""

from PyQt6.QtCore import QRunnable, QObject, pyqtSignal, pyqtSlot


class WorkerSignals(QObject):
    progress = pyqtSignal(str)
    result = pyqtSignal(object)
    error = pyqtSignal(str)
    finished = pyqtSignal()


class FollowingWorker(QRunnable):
    """Scrape the following list for a username."""

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            from scraper import scrape_following
            following = scrape_following(
                self.username,
                progress_cb=self.signals.progress.emit,
            )
            self.signals.result.emit(following)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class ProfileWorker(QRunnable):
    """Scrape a single user's profile info."""

    def __init__(self, username: str):
        super().__init__()
        self.username = username
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        try:
            from scraper import scrape_profile
            data = scrape_profile(self.username)
            self.signals.result.emit(data)
        except Exception as exc:
            self.signals.error.emit(str(exc))
        finally:
            self.signals.finished.emit()


class AnalysisWorker(QRunnable):
    """Scrape both users' ratings and run analysis."""

    def __init__(self, username1: str, username2: str, tmdb_key: str):
        super().__init__()
        self.username1 = username1
        self.username2 = username2
        self.tmdb_key = tmdb_key
        self.signals = WorkerSignals()

    @pyqtSlot()
    def run(self):
        import os
        os.environ["TMDB_API_KEY"] = self.tmdb_key

        try:
            from scraper import scrape_ratings, enrich_genres
            from analysis import run_analysis

            self.signals.progress.emit(f"Scraping {self.username1}…")
            df1 = scrape_ratings(self.username1, self.signals.progress.emit)

            self.signals.progress.emit(f"Scraping {self.username2}…")
            df2 = scrape_ratings(self.username2, self.signals.progress.emit)

            self.signals.progress.emit("Loading genres…")
            df1 = enrich_genres(df1, self.signals.progress.emit)
            df2 = enrich_genres(df2, self.signals.progress.emit)

            self.signals.progress.emit("Running analysis…")
            result = run_analysis(df1, df2)
            result["df1"] = df1
            result["df2"] = df2
            self.signals.result.emit(result)
        except Exception as exc:
            import traceback
            self.signals.error.emit(traceback.format_exc())
        finally:
            self.signals.finished.emit()
