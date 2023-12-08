from yt_dlp.update import version_tuple
from yt_dlp.version import __version__

if version_tuple(__version__) < (2023, 9, 24):
    raise ImportError('yt-dlp version 2023.09.24 or later is required to use the TTUser plugin')

import itertools
import random
import string
import time

from yt_dlp.utils import ExtractorError, int_or_none, traverse_obj
from yt_dlp.extractor.tiktok import TikTokIE, TikTokUserIE


class TikTokUser_TTUserIE(TikTokUserIE, plugin_name='TTUser'):
    IE_NAME = 'tiktok:user'
    _VALID_URL = r'https?://(?:www\.)?tiktok\.com/@(?P<id>[\w\.-]+)/?(?:$|[#?])'
    _WORKING = True
    _TESTS = [{
        'url': 'https://tiktok.com/@therock?lang=en',
        'playlist_mincount': 25,
        'info_dict': {
            'id': 'therock',
        },
    }]

    _USER_AGENT = 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:115.0) Gecko/20100101 Firefox/115.0'
    _API_BASE_URL = 'https://www.tiktok.com/api/creator/item_list/'

    def _build_web_query(self, sec_uid, cursor):
        return {
            'aid': '1988',
            'app_language': 'en',
            'app_name': 'tiktok_web',
            'browser_language': 'en-US',
            'browser_name': 'Mozilla',
            'browser_online': 'true',
            'browser_platform': 'Win32',
            'browser_version': '5.0 (Windows)',
            'channel': 'tiktok_web',
            'cookie_enabled': 'true',
            'count': '15',
            'cursor': cursor,
            'device_id': ''.join(random.choices(string.digits, k=19)),
            'device_platform': 'web_pc',
            'focus_state': 'true',
            'from_page': 'user',
            'history_len': '2',
            'is_fullscreen': 'false',
            'is_page_visible': 'true',
            'language': 'en',
            'os': 'windows',
            'priority_region': '',
            'referer': '',
            'region': 'US',
            'screen_height': '1080',
            'screen_width': '1920',
            'secUid': sec_uid,
            'type': '1',  # pagination type: 0 == oldest-to-newest, 1 == newest-to-oldest
            'tz_name': 'UTC',
            'verifyFp': 'verify_%s' % ''.join(random.choices(string.hexdigits, k=7)),
            'webcast_language': 'en',
        }

    def _entries(self, sec_uid, user_name):
        print("entering entries")
        cursor = int(time.time() * 1E3)
        for page in itertools.count(1):
            print("cursor")
            response = self._download_json(
                self._API_BASE_URL, user_name, f'Downloading page {page}',
                query=self._build_web_query(sec_uid, cursor), headers={'User-Agent': self._USER_AGENT})

            for video in traverse_obj(response, ('itemList', lambda _, v: v['id'])):
                video_id = video['id']

                print(video_id)
                feed_list = self._call_api(
                    'feed', {'aweme_id': aweme_id}, aweme_id, note='Downloading video feed',
                    errnote='Unable to download video feed').get('aweme_list') or []
                aweme_detail = next((aweme for aweme in feed_list if str(aweme.get('aweme_id')) == aweme_id), None)
                aweme_id = aweme_detail['aweme_id']
                video_info = aweme_detail['video']
        
                known_resolutions = {}
        
                # Hack: Add direct video links first to prioritize them when removing duplicate formats
                formats = []
            
        
                self._remove_duplicate_formats(formats)
                auth_cookie = self._get_cookies(self._WEBPAGE_HOST).get('sid_tt')
                if auth_cookie:
                    for f in formats:
                        self._set_cookie(compat_urllib_parse_urlparse(f['url']).hostname, 'sid_tt', auth_cookie.value)
        
                thumbnails = []
                for cover_id in ('cover', 'ai_dynamic_cover', 'animated_cover', 'ai_dynamic_cover_bak',
                                 'origin_cover', 'dynamic_cover'):
                    for cover_url in traverse_obj(video_info, (cover_id, 'url_list', ...)):
                        thumbnails.append({
                            'id': cover_id,
                            'url': cover_url,
                        })
        
                stats_info = aweme_detail.get('statistics') or {}
                author_info = aweme_detail.get('author') or {}
                music_info = aweme_detail.get('music') or {}
                user_url = self._UPLOADER_URL_FORMAT % (traverse_obj(author_info,
                                                                     'sec_uid', 'id', 'uid', 'unique_id',
                                                                     expected_type=str_or_none, get_all=False))
                labels = traverse_obj(aweme_detail, ('hybrid_label', ..., 'text'), expected_type=str)
        
                contained_music_track = traverse_obj(
                    music_info, ('matched_song', 'title'), ('matched_pgc_sound', 'title'), expected_type=str)
                contained_music_author = traverse_obj(
                    music_info, ('matched_song', 'author'), ('matched_pgc_sound', 'author'), 'author', expected_type=str)
        
                is_generic_og_trackname = music_info.get('is_original_sound') and music_info.get('title') == 'original sound - %s' % music_info.get('owner_handle')
                if is_generic_og_trackname:
                    music_track, music_author = contained_music_track or 'original sound', contained_music_author
                else:
                    music_track, music_author = music_info.get('title'), music_info.get('author')
        
                yield {
                    'id': aweme_id,
                    'extractor_key': TikTokIE.ie_key(),
                    'extractor': TikTokIE.IE_NAME,
                    'webpage_url': self._create_url(author_info.get('uid'), aweme_id),
                    **traverse_obj(aweme_detail, {
                        'title': ('desc', {str}),
                        'description': ('desc', {str}),
                        'timestamp': ('create_time', {int_or_none}),
                    }),
                    **traverse_obj(stats_info, {
                        'view_count': 'play_count',
                        'like_count': 'digg_count',
                        'repost_count': 'share_count',
                        'comment_count': 'comment_count',
                    }, expected_type=int_or_none),
                    **traverse_obj(author_info, {
                        'uploader': 'unique_id',
                        'uploader_id': 'uid',
                        'creator': 'nickname',
                        'channel_id': 'sec_uid',
                    }, expected_type=str_or_none),
                    'uploader_url': user_url,
                    'track': music_track,
                    'album': str_or_none(music_info.get('album')) or None,
                    'artist': music_author or None,
                    'formats': formats,
                    'subtitles': self.extract_subtitles(aweme_detail, aweme_id),
                    'thumbnails': thumbnails,
                    'duration': int_or_none(traverse_obj(video_info, 'duration', ('download_addr', 'duration')), scale=1000),
                    'availability': self._availability(
                        is_private='Private' in labels,
                        needs_subscription='Friends only' in labels,
                        is_unlisted='Followers only' in labels),
                    '_format_sort_fields': ('quality', 'codec', 'size', 'br'),
                }
                if not aweme_detail:
                    raise ExtractorError('Unable to find video in feed', video_id=aweme_id)

            old_cursor = cursor
            print("traversing")
            cursor = traverse_obj(
                response, ('itemList', -1, 'createTime', {lambda x: x * 1E3}, {int_or_none}))
            if not cursor:
                cursor = old_cursor - 604800000  # jump 1 week back in time
            if cursor < 1472706000000 or not traverse_obj(response, 'hasMorePrevious'):
                break

    def _get_sec_uid(self, user_url, user_name, msg):
        webpage = self._download_webpage(
            user_url, user_name, fatal=False, headers={'User-Agent': 'Mozilla/5.0'},
            note=f'Downloading {msg} webpage', errnote=f'Unable to download {msg} webpage') or ''
        sec_uid = traverse_obj(self._search_json(
            r'<script[^>]+\bid="__UNIVERSAL_DATA_FOR_REHYDRATION__"[^>]*>', webpage,
            'rehydration data', user_name, end_pattern=r'</script>', default={}),
            ('__DEFAULT_SCOPE__', 'webapp.user-detail', 'userInfo', 'user', 'secUid', {str}))

        #print("exiting secuid")

        if sec_uid:
            return sec_uid
        try:
            return traverse_obj(
                self._get_sigi_state(webpage, user_name),
                ('LiveRoom', 'liveRoomUserInfo', 'user', 'secUid'),
                ('UserModule', 'users', ..., 'secUid'),
                get_all=False, expected_type=str)
        except ExtractorError:
            return None

    def _real_extract(self, url):
        user_name = self._match_id(url)
        sec_uid = self._configuration_arg('sec_uid', [None], ie_key=TikTokIE, casesense=True)[0]

        if not sec_uid:
            for user_url, msg in (
                (self._UPLOADER_URL_FORMAT % user_name, 'user'),
                (self._UPLOADER_URL_FORMAT % f'{user_name}/live', 'live'),
            ):
                sec_uid = self._get_sec_uid(user_url, user_name, msg)
                if sec_uid:
                    break

        if not sec_uid:
            webpage = self._download_webpage(
                f'https://www.tiktok.com/embed/@{user_name}', user_name,
                note='Downloading user embed page', fatal=False) or ''
            data = traverse_obj(self._search_json(
                r'<script[^>]+\bid=[\'"]__FRONTITY_CONNECT_STATE__[\'"][^>]*>',
                webpage, 'data', user_name, default={}),
                ('source', 'data', f'/embed/@{user_name}', {dict}))

            for aweme_id in traverse_obj(data, ('videoList', ..., 'id')):
                try:
                    sec_uid = self._extract_aweme_app(aweme_id).get('channel_id')
                except ExtractorError:
                    continue
                if sec_uid:
                    break

            if not sec_uid:
                raise ExtractorError(
                    'Could not extract secondary user ID. '
                    'Try using  --extractor-arg "tiktok:sec_uid=ID"  with your command, '
                    'replacing "ID" with the channel_id of the requested user')

        entries = self._entries(sec_uid, user_name)
        print("playlist!")
        result = self.playlist_result(entries, user_name)
        print("exiting extract") 
        return result


__all__ = []
