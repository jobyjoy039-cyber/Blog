"""Image generation using OpenAI DALL-E 3. Claude generates the prompt, DALL-E renders it."""
import os
import json
from typing import Optional
import anthropic

try:
    import openai
    OPENAI_AVAILABLE = True
except ImportError:
    OPENAI_AVAILABLE = False


class ImageGenerator:
    def __init__(self, anthropic_client: anthropic.Anthropic, openai_api_key: Optional[str] = None):
        self.claude = anthropic_client
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")

    def generate_image_prompts(self, article_content: str, topic: str, num_images: int = 3) -> list[dict]:
        """Use Claude to generate detailed DALL-E image prompts for the article."""
        # Call Claude (non-deep-research) to generate image prompts
        # System: expert art director generating photorealistic image prompts
        # Returns JSON: [{"position": "hero", "prompt": "...", "alt_text": "...", "style": "photorealistic"}]
        response = self.claude.messages.create(
            model="claude-opus-4-7",
            max_tokens=2048,
            system="You are an expert art director. Generate detailed DALL-E 3 image prompts for blog articles. Return a JSON array of image objects.",
            messages=[{
                "role": "user",
                "content": f"Generate {num_images} image prompts for a blog article about: {topic}\n\nArticle excerpt:\n{article_content[:2000]}\n\nReturn JSON array: [{{\"position\": \"hero|inline|conclusion\", \"prompt\": \"detailed DALL-E prompt\", \"alt_text\": \"SEO alt text\", \"style\": \"photorealistic\"}}]"
            }]
        )
        text = response.content[0].text
        # Strip JSON fences
        if "```json" in text:
            text = text.split("```json")[1].split("```")[0].strip()
        elif "```" in text:
            text = text.split("```")[1].split("```")[0].strip()
        return json.loads(text)

    def render_images(self, image_prompts: list[dict], output_dir: str = "outputs/images") -> list[dict]:
        """Render image prompts using DALL-E 3."""
        if not OPENAI_AVAILABLE:
            raise ImportError("openai package required: pip install openai")
        if not self.openai_key:
            raise ValueError("OPENAI_API_KEY not set")

        import openai as oai
        client = oai.OpenAI(api_key=self.openai_key)
        os.makedirs(output_dir, exist_ok=True)
        results = []
        for i, img in enumerate(image_prompts):
            resp = client.images.generate(
                model="dall-e-3",
                prompt=img["prompt"],
                size="1792x1024",
                quality="hd",
                n=1,
            )
            results.append({
                "position": img.get("position", f"image_{i}"),
                "url": resp.data[0].url,
                "alt_text": img.get("alt_text", ""),
                "revised_prompt": resp.data[0].revised_prompt,
            })
        return results

    def generate_and_render(self, article_content: str, topic: str, output_dir: str = "outputs/images") -> list[dict]:
        """Full pipeline: Claude generates prompts → DALL-E renders them."""
        prompts = self.generate_image_prompts(article_content, topic)
        return self.render_images(prompts, output_dir)
