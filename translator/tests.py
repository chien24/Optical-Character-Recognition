import json
from unittest.mock import Mock, patch

from django.test import SimpleTestCase
from django.urls import reverse

from translator.services import ERROR_PREFIX, translate_text


class TranslatorServiceTests(SimpleTestCase):
    @patch("translator.services.requests.get")
    def test_translate_text_uses_free_google_endpoint(self, mock_get):
        response = Mock()
        response.json.return_value = [
            [["Xin chao", "Hello", None, None, 10]],
            None,
            "en",
        ]
        response.raise_for_status.return_value = None
        mock_get.return_value = response

        translated = translate_text("Hello", target_language="vi", source_language="en")

        self.assertEqual(translated, "Xin chao")
        _, kwargs = mock_get.call_args
        self.assertEqual(kwargs["params"]["client"], "gtx")
        self.assertEqual(kwargs["params"]["sl"], "en")
        self.assertEqual(kwargs["params"]["tl"], "vi")
        self.assertEqual(kwargs["params"]["q"], "Hello")

    @patch("translator.services.requests.get")
    def test_translate_text_returns_error_prefix_on_failure(self, mock_get):
        mock_get.side_effect = RuntimeError("network down")

        translated = translate_text("Hello", target_language="vi", source_language="en")

        self.assertTrue(translated.startswith(ERROR_PREFIX))


class TranslatorApiTests(SimpleTestCase):
    @patch("translator.views.translate_text", return_value="Xin chao")
    def test_translate_api_returns_translated_text(self, mock_translate):
        response = self.client.post(
            reverse("translator:translate_api"),
            data=json.dumps(
                {
                    "source_text": "Hello",
                    "source_language": "en",
                    "target_language": "vi",
                }
            ),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["translated_text"], "Xin chao")
        mock_translate.assert_called_once_with(
            "Hello",
            target_language="vi",
            source_language="en",
        )

    def test_translate_api_rejects_empty_text(self):
        response = self.client.post(
            reverse("translator:translate_api"),
            data=json.dumps({"source_text": "   "}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertFalse(response.json()["ok"])

    @patch("translator.views.translate_text", return_value=f"{ERROR_PREFIX} failed")
    def test_translate_api_returns_bad_gateway_on_provider_error(self, _mock_translate):
        response = self.client.post(
            reverse("translator:translate_api"),
            data=json.dumps({"source_text": "Hello"}),
            content_type="application/json",
        )

        self.assertEqual(response.status_code, 502)
        self.assertFalse(response.json()["ok"])
