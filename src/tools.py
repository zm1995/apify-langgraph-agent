"""Module defines the tools used by the agent.

Feel free to modify or add new tools to suit your specific needs.

To learn how to create a new tool, see:
- https://python.langchain.com/docs/concepts/tools/
- https://python.langchain.com/docs/how_to/#tools
"""

from __future__ import annotations

from apify import Actor
from langchain_core.tools import tool

import asyncio
from crawlee.crawlers import BeautifulSoupCrawler, BeautifulSoupCrawlingContext
from models import YouTubeVideo

# @tool
# def tool_calculator_sum(numbers: list[int]) -> int:
#     """Tool to calculate the sum of a list of numbers.

#     Args:
#         numbers (list[int]): List of numbers to sum.

#     Returns:
#         int: Sum of the numbers.
#     """
#     return sum(numbers)


# @tool
# async def tool_scrape_instagram_profile_posts(handle: str, max_posts: int = 30) -> list[InstagramPost]:
#     """Tool to scrape Instagram profile posts.

#     Args:
#         handle (str): Instagram handle of the profile to scrape (without the '@' symbol).
#         max_posts (int, optional): Maximum number of posts to scrape. Defaults to 30.

#     Returns:
#         list[InstagramPost]: List of Instagram posts scraped from the profile.

#     Raises:
#         RuntimeError: If the Actor fails to start.
#     """
#     run_input = {
#         'directUrls': [f'https://www.instagram.com/{handle}/'],
#         'resultsLimit': max_posts,
#         'resultsType': 'posts',
#         'searchLimit': 1,
#     }
#     if not (run := await Actor.apify_client.actor('apify/instagram-scraper').call(run_input=run_input)):
#         msg = 'Failed to start the Actor apify/instagram-scraper'
#         raise RuntimeError(msg)

#     dataset_id = run['defaultDatasetId']
#     dataset_items: list[dict] = (await Actor.apify_client.dataset(dataset_id).list_items()).items
#     posts: list[InstagramPost] = []
#     for item in dataset_items:
#         url: str | None = item.get('url')
#         caption: str | None = item.get('caption')
#         alt: str | None = item.get('alt')
#         likes: int | None = item.get('likesCount')
#         comments: int | None = item.get('commentsCount')
#         timestamp: str | None = item.get('timestamp')

#         # only include posts with all required fields
#         if not url or not likes or not comments or not timestamp:
#             Actor.log.warning('Skipping post with missing fields: %s', item)
#             continue

#         posts.append(
#             InstagramPost(
#                 url=url,
#                 likes=likes,
#                 comments=comments,
#                 timestamp=timestamp,
#                 caption=caption,
#                 alt=alt,
#             )
#         )

#     return posts


@tool
async def tool_scrape_youtube_30_posts(handle: str, max_videos: int = 30) -> list[YouTubeVideo]:
    """Tool to scrape YouTube channel videos.

    Args:
        handle (str): YouTube channel handle to scrape (without the '@' symbol).
        max_videos (int, optional): Maximum number of videos to scrape. Defaults to 30.

    Returns:
        list[YouTubeVideo]: List of YouTube video scraped from the channel.
    """
    crawler = BeautifulSoupCrawler()

    @crawler.router.default_handler
    async def handle_listing(context: BeautifulSoupCrawlingContext):
        context.log.info("Looking for video detail pages")
        await context.enqueue_links(selector="ytd-rich-item-renderer a.yt-simple-endpoint.style-scope.yt-formatted-link", label="DETAIL")

    @crawler.router.handler("DETAIL")
    async def handle_detail(context: BeautifulSoupCrawlingContext):
        context.log.info(f"Found video: {context.request.url}")
        await context.push_data(YouTubeVideo(title=context.soup.select_one("ytd-video-title").text.strip(), url=context.request.url, views=context.soup.select_one("span.view-count").text.strip(), duration=context.soup.select_one("span.duration").text.strip(), channel=context.soup.select_one("ytd-channel-name a").text.strip(), published_at=context.soup.select_one("span.published-time").text.strip()))

    await crawler.run(["https://www.youtube.com/"])

    crawler.log.info("Exporting data")
    await crawler.export_data(path='dataset.json', ensure_ascii=False, indent=2)
    await crawler.export_data(path='dataset.csv')

