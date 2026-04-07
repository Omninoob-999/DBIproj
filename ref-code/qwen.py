#!/usr/bin/env python3
"""Amazon Bedrock Qwen3-VL-235B-A22B Test Script (Bearer Token Auth)"""

import os
import json
import base64
import requests
from dotenv import load_dotenv
from pathlib import Path

# Load environment variables
load_dotenv()


def encode_image_to_base64(image_path: str) -> str:
    with open(image_path, "rb") as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def get_bedrock_config():
    bearer_token = os.getenv('AWS_BEARER_TOKEN_BEDROCK')
    endpoint = os.getenv('BEDROCK_ENDPOINT', 'https://bedrock-runtime.us-east-1.amazonaws.com')
    model_id = os.getenv('BEDROCK_MODEL_ID', 'qwen.qwen3-vl-235b-a22b')

    if not bearer_token:
        raise ValueError("AWS_BEARER_TOKEN_BEDROCK not found in .env file")

    return bearer_token, endpoint, model_id


def test_vision_prompt(bearer_token: str, endpoint: str, model_id: str, image_path: str, prompt: str):
    print(f"\nTesting Qwen3-VL with image: {image_path}")
    print(f"Prompt: {prompt}")

    image_base64 = encode_image_to_base64(image_path)

    headers = {
        "Authorization": f"Bearer {bearer_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }

    # Test 1: /converse endpoint (standardized Messages API)
    print("\n" + "="*60)
    print("TEST 1: /converse endpoint (Messages API)")
    print("="*60)

    converse_body = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image",
                        "image": {
                            "format": "jpeg",
                            "source": {
                                "bytes": image_base64
                            }
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }

    converse_url = f"{endpoint}/model/{model_id}/converse"
    print(f"URL: {converse_url}")

    response = requests.post(converse_url, headers=headers, json=converse_body)
    print(f"Status: {response.status_code}")

    if response.status_code == 200:
        response_body = response.json()
        print("\n--- /converse Response ---")
        if 'output' in response_body:
            message = response_body['output'].get('message', {})
            content = message.get('content', [])
            if content and isinstance(content, list):
                for item in content:
                    if 'text' in item:
                        print(item['text'])
        print("\nconverse endpoint: SUCCESS")
    else:
        print(f"Error: {response.text[:300]}")
        print("\nconverse endpoint: FAILED")


    # Test 2: /invoke endpoint - try multiple formats
    print("\n" + "="*60)
    print("TEST 2: /invoke endpoint (Trying multiple formats)")
    print("="*60)

    invoke_url = f"{endpoint}/model/{model_id}/invoke"
    print(f"URL: {invoke_url}")

    # Format 1: OpenAI-compatible format
    print("\n--- Format 1: OpenAI-compatible ---")
    invoke_body_1 = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": f"data:image/jpeg;base64,{image_base64}"
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
            }
        ],
        "max_tokens": 512,
        "temperature": 0.7
    }

    response = requests.post(invoke_url, headers=headers, json=invoke_body_1)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS with Format 1!")
        response_body = response.json()
        if 'choices' in response_body:
            print(response_body['choices'][0].get('message', {}).get('content', ''))
        else:
            print(json.dumps(response_body, indent=2))
    else:
        print(f"Failed: {response.text[:200]}")

    # Format 2: Qwen native format (text + image)
    print("\n--- Format 2: Qwen native (content array) ---")
    invoke_body_2 = {
        "input": {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {
                            "image": f"data:image/jpeg;base64,{image_base64}"
                        },
                        {
                            "text": prompt
                        }
                    ]
                }
            ]
        },
        "parameters": {
            "max_tokens": 512,
            "temperature": 0.7
        }
    }

    response = requests.post(invoke_url, headers=headers, json=invoke_body_2)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS with Format 2!")
        response_body = response.json()
        print(json.dumps(response_body, indent=2))
    else:
        print(f"Failed: {response.text[:200]}")

    # Format 3: Simple text-only (for comparison)
    print("\n--- Format 3: Text-only (baseline test) ---")
    invoke_body_3 = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {
                        "type": "text",
                        "text": "Hello, please respond with just: SUCCESS"
                    }
                ]
            }
        ],
        "max_tokens": 100,
        "temperature": 0.7
    }

    response = requests.post(invoke_url, headers=headers, json=invoke_body_3)
    print(f"Status: {response.status_code}")
    if response.status_code == 200:
        print("SUCCESS with text-only!")
        response_body = response.json()
        print(json.dumps(response_body, indent=2))
    else:
        print(f"Failed: {response.text[:200]}")


def create_test_image():
    """Create a simple test image with shapes and text."""
    from PIL import Image, ImageDraw

    img = Image.new('RGB', (400, 200), color='white')
    draw = ImageDraw.Draw(img)
    draw.rectangle([50, 50, 150, 150], fill='blue', outline='black')
    draw.ellipse([200, 50, 300, 150], fill='red', outline='black')
    draw.text((50, 170), "Test Image for Qwen3-VL", fill='black')

    test_path = "/tmp/test_qwen_image.jpg"
    img.save(test_path, 'JPEG')
    return test_path


def main():
    print("="*60)
    print("Amazon Bedrock - Qwen3-VL-235B-A22B Test")
    print("="*60)

    bearer_token, endpoint, model_id = get_bedrock_config()

    # Show config (without exposing token)
    print(f"Endpoint: {endpoint}")
    print(f"Model: {model_id}")
    print(f"Token: {bearer_token[:20]}...{bearer_token[-10:]}")

    # Create test image
    test_image = create_test_image()
    print(f"Created test image: {test_image}")

    # Run vision test
    test_vision_prompt(
        bearer_token, endpoint, model_id, test_image,
        "Describe this image in detail. What shapes and colors do you see?"
    )

    # Cleanup
    Path(test_image).unlink()
    print("\nTest completed!")


if __name__ == "__main__":
    main()
