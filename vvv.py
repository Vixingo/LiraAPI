import requests
import json
import re
cookies = {
    'sb': 'dmyFaj5iaZoAIc4FhIySpicd',
    'datr': 'wUSGarEZq4dRT2NrY_yYbewu',
    'ps_l': '1',
    'ps_n': '1',
    'c_user': '100091706204954',
    'dpr': '0.8999999761581421',
    'wd': '1358x610',
    'presence': 'C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1790415221669%2C%22v%22%3A1%7D',
    'fr': '1MaZqShHochqQtp20.AWctAv7LDbZIexhTG3vbTFH9DSdI3AMwAkhB2AtNc01cA9lP_ok.Bqt5GT..AAA.0.0.Bqt5GT.AWcohtmYRMuMUtmntGEvLLMiwUI',
    'xs': '47%3Acq0aOS8jB1lXwQ%3A2%3A1787184336%3A-1%3A-1%3A%3AAcz6P0ECxYXehjVBVUy43QJv1EsfthE40oBS9hMA3Ig',
}

headers = {
    'accept': '*/*',
    'accept-language': 'en-US,en;q=0.9',
    'content-type': 'application/x-www-form-urlencoded',
    'origin': 'https://www.facebook.com',
    'priority': 'u=1, i',
    'referer': 'https://www.facebook.com/cb.gov.sy/?locale=ar_AR',
    'sec-ch-prefers-color-scheme': 'light',
    'sec-ch-ua': '"Microsoft Edge";v="153", "Not_A Brand";v="8", "Chromium";v="153"',
    'sec-ch-ua-full-version-list': '"Microsoft Edge";v="153.0.4234.48", "Not_A Brand";v="8.0.0.0", "Chromium";v="153.0.8010.53"',
    'sec-ch-ua-mobile': '?0',
    'sec-ch-ua-model': '""',
    'sec-ch-ua-platform': '"Windows"',
    'sec-ch-ua-platform-version': '"10.0.0"',
    'sec-fetch-dest': 'empty',
    'sec-fetch-mode': 'cors',
    'sec-fetch-site': 'same-origin',
    'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/153.0.0.0 Safari/537.36 Edg/153.0.0.0',
    'x-asbd-id': '359341',
    'x-fb-friendly-name': 'ProfileCometTimelineFeedRefetchQuery',
    'x-fb-lsd': 'xpVHDDH5B9MJQ6t33ndHQK',
    # 'cookie': 'sb=dmyFaj5iaZoAIc4FhIySpicd; datr=wUSGarEZq4dRT2NrY_yYbewu; ps_l=1; ps_n=1; c_user=100091706204954; dpr=0.8999999761581421; wd=1358x610; presence=C%7B%22t3%22%3A%5B%5D%2C%22utc3%22%3A1790415221669%2C%22v%22%3A1%7D; fr=1MaZqShHochqQtp20.AWctAv7LDbZIexhTG3vbTFH9DSdI3AMwAkhB2AtNc01cA9lP_ok.Bqt5GT..AAA.0.0.Bqt5GT.AWcohtmYRMuMUtmntGEvLLMiwUI; xs=47%3Acq0aOS8jB1lXwQ%3A2%3A1787184336%3A-1%3A-1%3A%3AAcz6P0ECxYXehjVBVUy43QJv1EsfthE40oBS9hMA3Ig',
}

data = {
    'av': '100091706204954',
    '__aaid': '0',
    '__user': '100091706204954',
    '__a': '1',
    '__req': '3r',
    '__hs': '20722.HYP:comet_pkg.2.1...0',
    'dpr': '1',
    '__ccg': 'GOOD',
    '__rev': '1048557256',
    '__s': 'cbo9va:tf6d9e:v3mnsy',
    '__hsi': '7689774564716572592',
    '__dyn': '7xeUjGU5a5Q1ryaxG4Vp41twWwIxu13wsoKbgS3q2ibwNw9G2Saw8i2S1DwUx60GE3Qwb-q7oc81EEbbwto886C11wBz83WwgEcEhwGxu782lwv89kbxS1FwnE6a1awhUC7Udo5qfK0zEkxe2GewyDwkUe9obrwh8lwUwOzEjUlDw-wUws9ovUaU3qxW2-awLyES1TwVwwwOg2ZwhEkxebwHwNxe6Uak0zU8oC1hxB0jUpwgUjz89oeE-5oabDzUiBG2OUqwlqwLwlE7m11zU1fUaUcEK6Eqwby0QUqwRyBxO1bw',
    '__csr': 'gfkv3JM9cQdMP6h4JOhi7q9sRMxsIXR9vF6ltaItEQ9iZtlm_pkRoRH8F5J6lQO9njshihlZ6AjW-_jGyfAsWz9bKF8xeByVrWaVJeAJ5R8AXGF95GRFmZBKFAH8i9mqnnoBaFrXh_QquiGBlaHmilaF-FeQl2qHGq9Bz6iqm8UyHlCZSauh9vOnBmmmkPupuiAm8CK8nh4A-vQ8yEB2emLcAnEzt5mTOO4GVuaoSaAwBF1G8aK8y9-9yXyQuby8jjDGVFVoCqLyEzgjDgtAAx53odUcoS8yu-ieK8yVoW2e4ahomKeCyEmBAS8qprUK3mi6UOufz9Eggjz8OmECaxe22cx62O7oC1ay-l3UdE9VQdDggzoryEjxifwWyodqwKxzxS4oK2Kt0CzqxK4EaUf8uwg8iwADAxa1qxy5U-dxG8gtwywyK8wOG3C3O1twkVF8nwZwtU1E8ty85J0Awmo6S1Aw8S58aU4CbG485e0B8iz80A-1KgW2G2C0-AWgdomxK1IG0wUoxi3jzU88S4-1FwSw2H80hezE0bkE0HC04xFo0HWto0Di1Gxe6odkUd8ow29o2kws605cUgwDa09tw0ahe01EhQ08RxPa03De2G0aAoO1-w1kF12082w2Go27c0dhw1aQU3Bw5Myk0No7G08Kg3Yg0G0geg0Aq0RFU0lpw3_S0hGkZ00yyQ4E0sFyo0Le0apz40awc1gw1KK0b3yBwqE4G5E4u',
    '__hsdp': 'gtgWwAgd9E88a89ERMygG58O5EoCz8eniaoyaAooG68eFEagwwUJ8bE88P349kPsf41iqga888fMAwNb4Niif6hz48gxoIwwONhmswpokr8y6uARFEAek8QpGAyh4F4yDnhZ7zR2gx188LpFciF6AEIgb2lcyqWgSqg4kdjOBtFAIV2RNsAyt2P5ygwx26EQ8EAF2gMCyEgiFcxk9gR2Aim4SyGUO2pDijBy69A50yhFAsiy111cEx34q2B9K12wSFaP0Mg86h2C17ghh68G8ho47zIw8y28QGUK3K8xG4C2dDjU6acxu7A0xUfaFCgS19grxWUhzVEOEGl6w70y82Tm1MBK36u3a351G1EwIU8i0jWyu3vgeUvwjbx62m6EpQU4B0sErw29ErwsfgKi6U762e0XU6u0S82Ow5XwqUiwfq1Fxu0FE5a09xwnUK0NE1d81MoOU08m80Mi0lO5EmwFxq0OE1bU2jwbS0qS1DwBw6CwHw8q1kw6bwrE4W3q0ui0A82Hwuo2wwce04qE5m0v60j63G0oq16w5Nw',
    '__hblp': '0wyGF0XwzwDK0A63O1vx-m22nx50ywo87e1OAwm-dxaew967Kbx23C1Mw_wjU5G6EfUgwj88ogxu13-1bwOwJwjU5maxe1SwFxe2K17xu5E490MK1AwAweilDzoZ0UxO5FXx6fxfgGl6wf10a22S8wJwjEeQ1TiwNhE66A6Eb89E465UW1iw8a7U524oboG1Own8myU-1hw4BwaW0AogxK1Nwzw961txu3qdyA10wwwQxSieUO0zE8UC0Do4Kq3m1awQwSxaq0XUaoswyxu6U5Cu2y1eK0Bo9o6G4o4W0jC0QE23www8-1Yw8O0GoScw4pw4BwYxi1OF044wb20Co4S1Rw7TxG2O0c4w5sxq5Eaomwb664bw4yw9e1Oyo425o1z8G1DwBweO0KpE99oc84d2F8C5obU2TzEtwLwtE6W1ewSw5kw8Z0-wGyogyE2cxW1Vwa24U7m6Utw4Wx-08txK2q1cwoo5aE4mu0h21dg4e0JUvxOmdxW14wMwVzU1kEsw5kx2',
    '__sjsp': 'gtgWwAgd9E88a89ERMygG58O5EoCz8eniaoyaAooG68eFEn4gwwUJ8bE88P6Yh2lcT3N0kyMwo88fMAB7OONckHf6hzakBHfyO2nAbgy886k5mSh2XAApu5-UGtGAhh28h9ylQ9gam8xeNHSq8zku24gSAVmt0BhEcy3FECh0xgig5Bpk7UBO0ygSbgG1xigjg591R1gw4xd0hEeEf42u1lgbA',
    '__comet_req': '15',
    'locale': 'ar_AR',
    'fb_dtsg': 'NAfx_h6gXOPbDE5ysmJFp5I5Bh9Qb34XTY9kqpf3pMCo6-WKuf8RVvw:47:1787184336',
    'jazoest': '25407',
    'lsd': 'xpVHDDH5B9MJQ6t33ndHQK',
    '__spin_r': '1048557256',
    '__spin_b': 'trunk',
    '__spin_t': '1790415160',
    '__crn': 'comet.fbweb.CometProfileTimelineListViewRoute',
    'fb_api_caller_class': 'RelayModern',
    'fb_api_req_friendly_name': 'ProfileCometTimelineFeedRefetchQuery',
    'server_timestamp   s': 'true',
    'variables': '{"afterTime":null,"beforeTime":null,"count":3,"cursor":"Cg8Ob3JnYW5pY19jdXJzb3IJAAACREFRSFRvRVNMYlp6YkRLUDNkc0tfLTJSbENwN3RrWFBkS0JuQ29HVFlKdUxzUE84dHVuOHZvV0I4ZHB3Q2dEc1dycVZBSnN3Q3MwMlR6ekJIVWhIOFdJMjNmQjJqWUdyVEVXd3NmZkZtakJYWWtUYk5PUmtRbUhhWFdWNi1kRng0QzE2cDFBOU95WE5DcjQwa0FTQ0tpelVrbU54YlFPVHMwTEhlU2RCVVFXY2VUUVpRZXdnbFU0ZjdJcVNBWGwwcUZpYmNHN2laVWJIYW1UcWVYR0hfbW0xZE50UF9QNkIxaEc4REJaSnZMb2dHMHRhaXZianRtWS02UFFRcU1QYzQyanZoNTl2eE9OaFQ4bW9IQV9WLVhrekxsU2FkalNVSjJhUTUxVHJ5WVlmdkVJTm51ZnE4bTN4VWZDamZuNThHRHZSWTd4ckRiTUhjczRDR2U1Q1RFRl9YWDhKQm5rby1MZUFJLUJrdGhZVlhBRnBxQ2c5VjFpUENtZWVkRDhCdXdLdmZ2Unh0bFRfbnpsMFo2THVud095RUUwazZvemhfeDZ1UXJRSjZ2c2NWTDRGTDQ5VHJub0pucWtpZTRoOEJPSXFtWl9XT19rdmt3c0VHaTRNYWdpeVJ4VjVtTG42aFNKS2lHYk00Z3RpLUw2OEFfUWhQSTRRYktWV2lDb0ZVYlZhYkJsOVFBRmJXc1NMVzdqSGs4bFpjUHVsdVRmYmE5WDVCbV9kQVJOTm5zbHk1U0doLUZ3RVZXTVRHRkhDX1ltSWoPCWFkX2N1cnNvcg4PD2dsb2JhbF9wb3NpdGlvbgIADwZvZmZzZXQCAA8QbGFzdF9hZF9wb3NpdGlvbgL/AQ==","feedLocation":"TIMELINE","feedbackSource":0,"focusCommentID":null,"memorializedSplitTimeFilter":null,"omitPinnedPost":true,"postedBy":{"group":"OWNER"},"privacy":null,"privacySelectorRenderLocation":"COMET_STREAM","referringStoryRenderLocation":null,"renderLocation":"timeline","run_with_continuation_key":true,"scale":1,"stream_count":1,"taggedInOnly":null,"trackingCode":null,"useDefaultActor":false,"id":"100069248257915","__relay_internal__pv__GHLShouldChangeAdIdFieldNamerelayprovider":true,"__relay_internal__pv__GHLShouldChangeSponsoredDataFieldNamerelayprovider":true,"__relay_internal__pv__CometFeedStory_enable_reactor_facepilerelayprovider":false,"__relay_internal__pv__CometFeedStory_enable_social_bubblesrelayprovider":false,"__relay_internal__pv__CometFeedStory_enable_post_permalink_white_space_clickrelayprovider":false,"__relay_internal__pv__CometUFICommentActionLinksRewriteEnabledrelayprovider":true,"__relay_internal__pv__CometUFICommentAvatarStickerAnimatedImagerelayprovider":false,"__relay_internal__pv__IsWorkUserrelayprovider":false,"__relay_internal__pv__TestPilotShouldIncludeDemoAdUseCaserelayprovider":false,"__relay_internal__pv__FBReels_deprecate_short_form_video_context_gkrelayprovider":true,"__relay_internal__pv__CometUFI_dedicated_comment_routable_dialog_gkrelayprovider":true,"__relay_internal__pv__FBReels_enable_view_dubbed_audio_type_gkrelayprovider":true,"__relay_internal__pv__CometFeedShareMedia_shouldPrefetchShareImagerelayprovider":false,"__relay_internal__pv__CometImmersivePhotoCanUserDisable3DMotionrelayprovider":false,"__relay_internal__pv__WorkCometIsEmployeeGKProviderrelayprovider":false,"__relay_internal__pv__IsMergQAPollsrelayprovider":false,"__relay_internal__pv__FBReelsMediaFooter_comet_enable_reels_ads_gkrelayprovider":false,"__relay_internal__pv__CometUFIReactionsEnableShortNamerelayprovider":false,"__relay_internal__pv__CometUFICommentAutoTranslationTyperelayprovider":"AUTO_TRANSLATE","__relay_internal__pv__CometUFIShareActionMigrationrelayprovider":true,"__relay_internal__pv__CometUFISingleLineUFIrelayprovider":true,"__relay_internal__pv__relay_provider_comet_ufi_ssr_seo_deferrelayprovider":true,"__relay_internal__pv__FBReelsIFUTileContent_reelsIFUPlayOnHoverrelayprovider":true,"__relay_internal__pv__GroupsCometGYSJFeedItemHeightrelayprovider":206,"__relay_internal__pv__StoriesShouldEnablePhotosensitiveContentWarningrelayprovider":false,"__relay_internal__pv__ShouldEnableBakedInTextStoriesrelayprovider":false,"__relay_internal__pv__StoriesShouldIncludeFbNotesrelayprovider":true}',
    'doc_id': '28739823445685778',
}


response = requests.post('https://www.facebook.com/api/graphql/', cookies=cookies, headers=headers, data=data)



try:

    content = response.text
    print(content)
    pattern = r'("rds"\s*:\s*\[\]\s*\}\}\}\}\})(.*)'
    clean_content = re.sub(pattern, r"\1", content, flags=re.DOTALL)
    parsed_json = json.loads(clean_content)
    print("Valid JSON!")
    # Accessing the message text:
    print(len(parsed_json["data"]["node"]["timeline_list_feed_units"]["edges"]))
    for node in parsed_json["data"]["node"]["timeline_list_feed_units"]["edges"]:
        try:
            message = node["node"]["message"]["text"]
            print(message)
        except:
            print("ERROR")

except json.JSONDecodeError as e:
    print(f"Invalid JSON: {e}")