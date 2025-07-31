import asyncio
from apify_client import ApifyClient
from utils.supabase_client import supabase, update_user_balance
from config import get_logger, config

logger = get_logger()

class TikTokService:
    """
    Manages all interactions with TikTok, including profile verification
    and listening to live stream events for multiple users.
    """
    def __init__(self):
        self.client = ApifyClient(config.APIFY_API_KEY)

    async def verify_user(self, username: str, code: str) -> dict:
        """
        Verifies a user by checking their TikTok bio for a specific code.

        Returns:
            A dictionary with verification status and the user's permanent ID.
        """
        query = {
            "excludePinnedPosts": False,
            "profiles": [
                username
            ],
            "shouldDownloadAvatars": False,
            "shouldDownloadCovers": False,
            "shouldDownloadSlideshowImages": False,
            "shouldDownloadSubtitles": False,
            "shouldDownloadVideos": False,
            "profileScrapeSections": [
                "videos"
            ],
            "profileSorting": "latest",
            "resultsPerPage": 1
        }

        try:
            run = self.client.actor("clockworks/tiktok-profile-scraper").call(run_input=query)
            if not run:
                raise Exception("No run found")
            
            res = [i for i in self.client.dataset(run["defaultDatasetId"]).iterate_items()]
            if not res:
                raise Exception("User not found")
            res = res[0]['authorMeta']

            if (user_id := res["id"]) and (signature := res.get("signature")) and code in signature:
                logger.info(f"[Verification] Success for {username}. User ID: {user_id}")
                return {"verified": True, "tiktok_id": user_id}
            else:
                logger.warning(f"[Verification] Failed for {username}: Code not found in bio.")
                return {"verified": False}
        except Exception as e:
            logger.error(f"[Verification] Error scraping profile for {username}: {e}")
            if "User not found" in str(e):
                raise e
            raise Exception("An internal scraping error occurred.")
           