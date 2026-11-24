import importlib.util
import unittest
from pathlib import Path
from unittest.mock import patch

from scripts.social_text import SITE_URL, clip_text, compose_instagram_caption, prepare_summary

ROOT = Path(__file__).resolve().parents[1]


def module(name):
    spec = importlib.util.spec_from_file_location(name, ROOT / 'scripts' / f'{name}.py')
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


class SocialTextTests(unittest.TestCase):
    def test_only_explicitly_permitted_summaries_are_used(self):
        for policy in ['headline_date_link_only', None, 'unknown', '']:
            self.assertEqual(prepare_summary({'content_policy': policy, 'summary': 'Text que no es pot reutilitzar.'}), '')
        for policy in ['short_factual_excerpt', 'generated_social_summary', 'summary_allowed']:
            self.assertEqual(prepare_summary({'content_policy': policy, 'summary': 'Text permès.'}), 'Text permès.')

    def test_numbers_dates_and_abbreviations_remain_grounded(self):
        item = {'content_policy': 'short_factual_excerpt', 'summary':
                'El Dr. Ramon atendrà el 24/11 a les 14.30 h. El servei es manté fins al 27/11. Una tercera frase.'}
        self.assertEqual(prepare_summary(item),
                         'El Dr. Ramon atendrà el 24/11 a les 14.30 h. El servei es manté fins al 27/11.')

    def test_empty_repeated_or_url_only_text_does_not_become_a_summary(self):
        for text in ['', '   ', 'Titular', 'https://example.test/article']:
            self.assertEqual(prepare_summary({'content_policy': 'short_factual_excerpt',
                                             'title': 'Titular', 'summary': text}), '')

    def test_complete_drupal_header_is_removed_but_event_dates_are_retained(self):
        text = "sarrom dv., 20/11/2026 - 10:46 20-Novembre-2026 L'Ajuntament atendrà el 24/11 a les 14.30 h."
        item = {'content_policy': 'short_factual_excerpt', 'summary': text}
        self.assertEqual(prepare_summary(item), "L'Ajuntament atendrà el 24/11 a les 14.30 h.")
        item['summary'] = '20/11/2026 - 10:46: inici de les activitats.'
        self.assertEqual(prepare_summary(item), item['summary'])

    def test_shortening_is_explicit_and_does_not_split_a_word(self):
        self.assertEqual(clip_text('Una frase completa i més informació', 18), 'Una frase…')
        text = prepare_summary({'content_policy': 'short_factual_excerpt', 'summary': 'Informació local ' * 80})
        self.assertLessEqual(len(text), 360)
        self.assertTrue(text.endswith('…'))

    def test_footer_and_original_full_url_are_preserved(self):
        original = 'https://example.test/article?tracking=' + 'x' * 600
        header = f'Informació original: {original}\n\nTitular\n\nFont: Entitat local'
        result = compose_instagram_caption(header, 'Informació detallada ' * 300, '', '#Sóller')
        self.assertLessEqual(len(result), 2200)
        self.assertIn(original, result)
        self.assertEqual(result.count(SITE_URL), 1)
        self.assertIn('Sóller Ara · ' + SITE_URL, result)
        self.assertTrue(result.endswith('#Sóller'))
        self.assertIn('…', result)

    def test_manual_source_reference_is_retained_when_body_is_long(self):
        original = 'https://www.facebook.com/story.php?story_fbid=123&id=456'
        references = f'Font original (Entitat): {original}'
        result = compose_instagram_caption('Titular\n\nNotícia completa: https://example.test/own',
                                            'Text propi ' * 500, references, '#Sóller #SollerAra')
        self.assertLessEqual(len(result), 2200)
        self.assertIn(original, result)
        self.assertIn(SITE_URL, result)
        self.assertTrue(result.endswith('#Sóller #SollerAra'))

    def test_existing_home_link_is_not_duplicated_but_article_links_are_distinct(self):
        result = compose_instagram_caption('Notícia completa: ' + SITE_URL, 'Text', '', '#Sóller')
        self.assertEqual(result.count(SITE_URL), 1)
        result = compose_instagram_caption('Notícia completa: ' + SITE_URL + 'noticies/article.html', 'Text', '', '')
        self.assertIn('Sóller Ara · ' + SITE_URL, result)

    def test_references_cannot_be_silently_truncated(self):
        with self.assertRaisesRegex(ValueError, 'referències obligatòries'):
            compose_instagram_caption('https://example.test/' + 'x' * 2400, '', '', '')

    def test_branding_never_breaks_an_otherwise_valid_long_caption(self):
        header = 'https://example.test/' + 'x' * 2140
        result = compose_instagram_caption(header, 'Optional prose', '', '#Sóller')
        self.assertLessEqual(len(result), 2200)
        self.assertIn(header, result)

    def test_home_footer_cannot_be_mistaken_for_an_article_identity(self):
        delivery = module('instagram_delivery')
        caption = compose_instagram_caption('Informació original: https://example.test/one\n\nFont: Entitat',
                                            'Text', '', '#Sóller')
        media = [{'id': 'remote-one', 'caption': caption}]
        self.assertEqual(delivery.matching_media(media, SITE_URL), [])
        self.assertEqual(delivery.matching_media(media, 'https://example.test/one', 'Entitat'), media)

    def test_optional_preparation_failure_uses_existing_safe_text(self):
        publish = module('publish_collected_social')
        item = {'title': 'Titular', 'source': 'Entitat', 'summary': 'Resum permès.',
                'content_policy': 'short_factual_excerpt', 'original_url': 'https://example.test/article'}
        with patch.object(publish, 'prepare_summary', side_effect=ValueError('Simulated preparation failure')):
            result = publish.instagram_caption(item)
            self.assertIn('Resum permès.', result)
            self.assertIn(SITE_URL, result)
            item['content_policy'] = 'headline_date_link_only'
            self.assertNotIn('Resum permès.', publish.instagram_caption(item))
            item['content_policy'] = 'unknown'
            self.assertNotIn('Resum permès.', publish.instagram_caption(item))

    def test_facebook_text_is_unchanged_and_both_instagram_paths_add_the_home_link(self):
        publish = module('publish_collected_social')
        item = {'title': 'Titular', 'source': 'Entitat', 'summary': 'Resum permès.',
                'content_policy': 'short_factual_excerpt', 'original_url': 'https://example.test/article'}
        self.assertEqual(publish.base_text(item),
                         'Informació original: https://example.test/article\n\nTitular\n\nFont: Entitat\n\nResum permès.')
        self.assertIn(SITE_URL, publish.instagram_caption(item))
        item['content_policy'] = 'headline_date_link_only'
        self.assertNotIn('Resum permès.', publish.instagram_caption(item))
        self.assertIn(SITE_URL, publish.instagram_caption(item))


if __name__ == '__main__':
    unittest.main()
