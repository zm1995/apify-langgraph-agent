"""Module defines the tools used by the agent.

Feel free to modify or add new tools to suit your specific needs.

To learn how to create a new tool, see:
- https://python.langchain.com/docs/concepts/tools/
- https://python.langchain.com/docs/how_to/#tools
"""

from __future__ import annotations

import re
from typing import Any

from apify import Actor
from crawlee.crawlers import PlaywrightCrawler, PlaywrightCrawlingContext
from langchain_core.tools import tool

from src.models import YouTubeVideo

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


def parse_views(views_text: str | None) -> int | None:
    """Parse views text to integer.

    Args:
        views_text: Text like "1.2M views" or "500K views" or "123 views".

    Returns:
        Integer representation of views, or None if parsing fails.
    """
    if not views_text:
        return None
    
    # Remove "views" and whitespace
    views_text = views_text.lower().replace('views', '').strip()
    
    # Extract number and multiplier
    match = re.search(r'([\d.]+)\s*([kmb]?)', views_text)
    if not match:
        return None
    
    number = float(match.group(1))
    multiplier = match.group(2)
    
    multipliers = {'k': 1000, 'm': 1000000, 'b': 1000000000}
    multiplier_value = multipliers.get(multiplier, 1)
    
    return int(number * multiplier_value)


@tool
async def tool_scrape_youtube_30_posts(url: str = 'https://www.youtube.com/', max_videos: int = 30) -> list[YouTubeVideo]:
    """Tool to scrape YouTube videos from a given URL using PlaywrightCrawler.

    Args:
        url (str, optional): YouTube URL to scrape. Defaults to 'https://www.youtube.com/'.
        max_videos (int, optional): Maximum number of videos to scrape. Defaults to 30.

    Returns:
        list[YouTubeVideo]: List of YouTube videos scraped from the URL.
    """
    videos: list[YouTubeVideo] = []
    
    # Create PlaywrightCrawler instance
    crawler = PlaywrightCrawler(
        max_requests_per_crawl=max_videos,
        headless=True,
    )
    
    @crawler.router.default_handler
    async def handle_page(context: PlaywrightCrawlingContext) -> None:
        """Handle the YouTube page and extract video information."""
        Actor.log.info(f'Processing page: {context.request.url}')
        
        # Wait for video elements to load
        await context.page.wait_for_selector('ytd-rich-item-renderer, ytd-video-renderer', timeout=10000)
        
        # Scroll to load more videos
        await context.page.evaluate('window.scrollTo(0, document.body.scrollHeight)')
        await context.page.wait_for_timeout(2000)  # Wait for lazy loading
        
        # Extract video information
        video_elements = await context.page.query_selector_all('ytd-rich-item-renderer, ytd-video-renderer')
        
        Actor.log.info(f'Found {len(video_elements)} video elements on page')
        
        for element in video_elements[:max_videos]:
            try:
                # Extract title
                title_element = await element.query_selector('a#video-title, #video-title-link')
                title = await title_element.get_attribute('title') if title_element else None
                if not title:
                    title_text = await title_element.inner_text() if title_element else None
                    title = title_text
                
                # Extract URL
                video_url = None
                if title_element:
                    href = await title_element.get_attribute('href')
                    if href:
                        video_url = f'https://www.youtube.com{href}' if href.startswith('/') else href
                
                # Extract channel name
                channel_element = await element.query_selector('ytd-channel-name a, #channel-name a')
                channel = await channel_element.inner_text() if channel_element else None
                
                # Extract views
                views_element = await element.query_selector('#metadata-line span, .ytd-video-meta-block span')
                views_text = await views_element.inner_text() if views_element else None
                views = parse_views(views_text)
                
                # Extract duration
                duration_element = await element.query_selector('span.style-scope.ytd-thumbnail-overlay-time-status-renderer')
                duration = await duration_element.inner_text() if duration_element else None
                
                # Extract published date (if available)
                published_at = None
                metadata_elements = await element.query_selector_all('#metadata-line span')
                if len(metadata_elements) > 1:
                    published_text = await metadata_elements[-1].inner_text()
                    published_at = published_text if published_text else None
                
                # Only add if we have at least title and URL
                if title and video_url:
                    videos.append(
                        YouTubeVideo(
                            title=title.strip(),
                            url=video_url,
                            views=views,
                            duration=duration.strip() if duration else None,
                            channel=channel.strip() if channel else None,
                            published_at=published_at.strip() if published_at else None,
                        )
                    )
                    Actor.log.debug(f'Extracted video: {title}')
                    
                    # Stop if we've reached the limit
                    if len(videos) >= max_videos:
                        break
                        
            except Exception as e:
                Actor.log.warning(f'Error extracting video element: {e}')
                continue
    
    # Run the crawler
    Actor.log.info(f'Starting PlaywrightCrawler to scrape YouTube from: {url}')
    await crawler.run([url])
    
    Actor.log.info(f'Successfully scraped {len(videos)} YouTube videos')
    return videos[:max_videos]

