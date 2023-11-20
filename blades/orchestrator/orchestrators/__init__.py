from .scraping import scraping_orchestration
from .spotting import spotting_orchestration
from .orchestrator import orchestrator_orchestration

ORCHESTRATORS = {
    'scraper': scraping_orchestration,
    'spotting': spotting_orchestration,
    'orchestrator': orchestrator_orchestration
}
