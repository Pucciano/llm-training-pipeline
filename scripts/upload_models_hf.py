#!/usr/bin/env python3
"""
Upload models to the private Hugging Face model repository.

This script uploads model checkpoints from the notebooks/outputs directory
and the GGUF model file to a private Hugging Face repository. It uses
environment variables for configuration and authentication.

Environment Variables:
    HF_HOME: Hugging Face home directory (default: ~/.cache/huggingface)
    HF_HUB_CACHE: Hugging Face hub cache directory (default: $HF_HOME/hub)
    HF_TOKEN: Hugging Face User Access Token for authentication
    HF_REPO_ID: Hugging Face repository ID (e.g., "username/model-name")
    HF_REPO_TYPE: Repository type (default: "model")
    HF_CREATE_REPO: Whether to create the repository if it doesn't exist (default: "true")
"""

import os
import sys
import logging
import argparse
from pathlib import Path
from typing import Optional, List

# Check if required packages are installed
try:
    from huggingface_hub import HfApi, upload_folder, upload_file, create_repo, login
    from huggingface_hub.utils import HfHubHTTPError
except ImportError:
    print("Error: huggingface_hub is not installed.")
    print("Please install it with: uv add huggingface_hub")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler('upload_models_hf.log')
    ]
)
logger = logging.getLogger(__name__)


class HuggingFaceUploader:
    """Handles uploading models to Hugging Face Hub."""

    def __init__(self):
        self.api = HfApi()
        self.setup_environment()
        self.authenticate()

    def setup_environment(self):
        """Setup environment variables with defaults."""
        # Set HF_HOME if not already set
        if 'HF_HOME' not in os.environ:
            xdg_cache_home = os.environ.get('XDG_CACHE_HOME')
            if xdg_cache_home:
                hf_home = os.path.join(xdg_cache_home, 'huggingface')
            else:
                hf_home = os.path.expanduser('~/.cache/huggingface')
            os.environ['HF_HOME'] = hf_home

        # Set HF_HUB_CACHE if not already set
        if 'HF_HUB_CACHE' not in os.environ:
            hf_home = os.environ['HF_HOME']
            os.environ['HF_HUB_CACHE'] = os.path.join(hf_home, 'hub')

        logger.info(f"HF_HOME: {os.environ['HF_HOME']}")
        logger.info(f"HF_HUB_CACHE: {os.environ['HF_HUB_CACHE']}")

    def authenticate(self):
        """Authenticate with Hugging Face Hub using HF_TOKEN."""
        token = os.environ.get('HF_TOKEN')
        if not token:
            raise ValueError(
                "HF_TOKEN environment variable is required for authentication. "
                "Please set it to your Hugging Face User Access Token."
            )

        try:
            login(token=token)
            logger.info("Successfully authenticated with Hugging Face Hub")
        except Exception as e:
            logger.error(f"Failed to authenticate with Hugging Face Hub: {e}")
            raise

    def find_checkpoints(self, models_dir: Path) -> List[Path]:
        """Find all checkpoint directories in the models directory."""
        if not models_dir.exists():
            raise FileNotFoundError(f"Models directory not found: {models_dir}")

        checkpoints = []
        for item in models_dir.iterdir():
            if item.is_dir() and item.name.startswith('checkpoint-'):
                checkpoints.append(item)

        checkpoints.sort(key=lambda x: int(x.name.split('-')[1]))
        logger.info(f"Found {len(checkpoints)} checkpoints: {[cp.name for cp in checkpoints]}")
        return checkpoints

    def find_gguf_model(self, gguf_path: Path) -> Optional[Path]:
        """Find the GGUF model file."""
        if gguf_path.exists() and gguf_path.is_file():
            logger.info(f"Found GGUF model: {gguf_path}")
            return gguf_path
        else:
            logger.warning(f"GGUF model not found at: {gguf_path}")
            return None

    def create_repository_if_needed(self, repo_id: str, private: bool = True) -> bool:
        """Create a repository if it doesn't exist and HF_CREATE_REPO is true."""
        create_repo_env = os.environ.get('HF_CREATE_REPO', 'true').lower()
        if create_repo_env not in ['true', '1', 'yes']:
            return False

        try:
            self.api.repo_info(repo_id=repo_id, repo_type="model")
            logger.info(f"Repository {repo_id} already exists")
            return False
        except HfHubHTTPError as e:
            if e.response.status_code == 404:
                logger.info(f"Creating repository {repo_id}")
                create_repo(
                    repo_id=repo_id,
                    repo_type="model",
                    private=private
                )
                logger.info(f"Successfully created repository {repo_id}")
                return True
            else:
                raise

    def upload_gguf_model(self, gguf_path: Path, repo_id: str,
                          commit_message: Optional[str] = None) -> bool:
        """Upload the GGUF model file to the repository root."""
        if not commit_message:
            commit_message = f"Upload GGUF model: {gguf_path.name}"

        try:
            logger.info(f"Uploading GGUF model {gguf_path.name} to {repo_id}")

            upload_file(
                path_or_fileobj=str(gguf_path),
                path_in_repo=gguf_path.name,
                repo_id=repo_id,
                repo_type="model",
                commit_message=commit_message
            )

            logger.info(f"Successfully uploaded GGUF model: {gguf_path.name}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload GGUF model {gguf_path.name}: {e}")
            return False

    def upload_checkpoint(self, checkpoint_dir: Path, repo_id: str,
                          commit_message: Optional[str] = None) -> bool:
        """Upload a single checkpoint to the repository."""
        checkpoint_name = checkpoint_dir.name

        if not commit_message:
            commit_message = f"Upload {checkpoint_name}"

        try:
            logger.info(f"Uploading {checkpoint_name} to {repo_id}")

            # Upload the entire checkpoint folder
            upload_folder(
                folder_path=str(checkpoint_dir),
                repo_id=repo_id,
                repo_type="model",
                path_in_repo=checkpoint_name,
                commit_message=commit_message,
                ignore_patterns=[
                    "*.log",
                    "*.tmp",
                    "__pycache__/",
                    "*.pyc",
                    ".DS_Store"
                ]
            )

            logger.info(f"Successfully uploaded {checkpoint_name}")
            return True

        except Exception as e:
            logger.error(f"Failed to upload {checkpoint_name}: {e}")
            return False

    def upload_all_models(self, models_dir: Path, gguf_path: Path, repo_id: str,
                          private: bool = True) -> dict:
        """Upload all models (checkpoints and GGUF) to the repository."""
        results = {
            'checkpoints': {'success': [], 'failed': []},
            'gguf': {'success': False, 'failed': False}
        }

        # Create a repository if needed
        self.create_repository_if_needed(repo_id, private)

        # Upload GGUF model first
        gguf_model = self.find_gguf_model(gguf_path)
        if gguf_model:
            success = self.upload_gguf_model(gguf_model, repo_id)
            results['gguf']['success'] = success
            if not success:
                results['gguf']['failed'] = True

        # Find and upload checkpoints
        checkpoints = self.find_checkpoints(models_dir)

        if not checkpoints:
            logger.warning("No checkpoints found to upload")
        else:
            # Upload each checkpoint
            for checkpoint_dir in checkpoints:
                success = self.upload_checkpoint(checkpoint_dir, repo_id)
                if success:
                    results['checkpoints']['success'].append(checkpoint_dir.name)
                else:
                    results['checkpoints']['failed'].append(checkpoint_dir.name)

        return results


def main():
    """Main function to handle command line arguments and run the upload."""
    parser = argparse.ArgumentParser(
        description="Upload model checkpoints and GGUF model to Hugging Face Hub",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Environment Variables:
  HF_TOKEN       Hugging Face User Access Token (required)
  HF_REPO_ID     Hugging Face repository ID (e.g., "username/model-name")
  HF_HOME        HF home directory (default: ~/.cache/huggingface)
  HF_HUB_CACHE   HF hub cache directory (default: $HF_HOME/hub)
  HF_CREATE_REPO Create repo if it doesn't exist (default: true)

Example:
  export HF_TOKEN="your-token-here"
  export HF_REPO_ID="your-username/your-model-name"
  python upload_models_hf.py
        """
    )

    parser.add_argument(
        '--models-dir',
        type=Path,
        default=Path('notebooks/outputs'),
        help='Directory containing model checkpoints (default: notebooks/outputs)'
    )

    parser.add_argument(
        '--gguf-path',
        type=Path,
        help='Path to GGUF model file'
    )

    parser.add_argument(
        '--repo-id',
        type=str,
        help='Hugging Face repository ID (can also use HF_REPO_ID env var)'
    )

    parser.add_argument(
        '--private',
        action='store_true',
        default=True,
        help='Create private repository (default: True)'
    )

    parser.add_argument(
        '--checkpoint',
        type=str,
        help='Upload only a specific checkpoint (e.g., checkpoint-60)'
    )

    parser.add_argument(
        '--gguf-only',
        action='store_true',
        help='Upload only the GGUF model file'
    )

    parser.add_argument(
        '--checkpoints-only',
        action='store_true',
        help='Upload only the checkpoint directories'
    )

    parser.add_argument(
        '--dry-run',
        action='store_true',
        help='Show what would be uploaded without actually uploading'
    )

    args = parser.parse_args()

    # Get repository ID from args or environment
    repo_id = args.repo_id or os.environ.get('HF_REPO_ID')
    if not repo_id:
        logger.error("Repository ID is required. Set --repo-id or HF_REPO_ID environment variable.")
        sys.exit(1)

    try:
        if args.dry_run:
            logger.info("DRY RUN MODE - No actual uploads will be performed")
            uploader = HuggingFaceUploader()

            if not args.checkpoints_only:
                gguf_model = uploader.find_gguf_model(args.gguf_path)
                if gguf_model:
                    logger.info(f"Would upload GGUF model: {gguf_model.name}")
                else:
                    logger.warning(f"GGUF model not found at: {args.gguf_path}")

            if not args.gguf_only:
                checkpoints = uploader.find_checkpoints(args.models_dir)
                if args.checkpoint:
                    target_checkpoint = args.models_dir / args.checkpoint
                    if target_checkpoint in checkpoints:
                        logger.info(f"Would upload checkpoint: {args.checkpoint}")
                    else:
                        logger.error(f"Checkpoint {args.checkpoint} not found")
                else:
                    logger.info(f"Would upload {len(checkpoints)} checkpoints to {repo_id}")
                    for checkpoint in checkpoints:
                        logger.info(f"  - {checkpoint.name}")
            return

        # Initialize uploader
        uploader = HuggingFaceUploader()

        # Create a repository if needed
        uploader.create_repository_if_needed(repo_id, args.private)

        if args.gguf_only:
            # Upload only GGUF model
            gguf_model = uploader.find_gguf_model(args.gguf_path)
            if not gguf_model:
                logger.error(f"GGUF model not found at: {args.gguf_path}")
                sys.exit(1)

            success = uploader.upload_gguf_model(gguf_model, repo_id)
            if success:
                logger.info("Successfully uploaded GGUF model")
            else:
                logger.error("Failed to upload GGUF model")
                sys.exit(1)

        elif args.checkpoints_only:
            # Upload only checkpoints
            if args.checkpoint:
                # Upload a specific checkpoint
                checkpoint_dir = args.models_dir / args.checkpoint
                if not checkpoint_dir.exists():
                    logger.error(f"Checkpoint directory not found: {checkpoint_dir}")
                    sys.exit(1)

                success = uploader.upload_checkpoint(checkpoint_dir, repo_id)
                if success:
                    logger.info(f"Successfully uploaded {args.checkpoint}")
                else:
                    logger.error(f"Failed to upload {args.checkpoint}")
                    sys.exit(1)
            else:
                # Upload all checkpoints
                checkpoints = uploader.find_checkpoints(args.models_dir)
                if not checkpoints:
                    logger.error("No checkpoints found to upload")
                    sys.exit(1)

                failed_checkpoints = []
                for checkpoint_dir in checkpoints:
                    success = uploader.upload_checkpoint(checkpoint_dir, repo_id)
                    if not success:
                        failed_checkpoints.append(checkpoint_dir.name)

                if failed_checkpoints:
                    logger.error(f"Failed to upload checkpoints: {failed_checkpoints}")
                    sys.exit(1)

        elif args.checkpoint:
            # Upload specific checkpoint only (no GGUF)
            checkpoint_dir = args.models_dir / args.checkpoint
            if not checkpoint_dir.exists():
                logger.error(f"Checkpoint directory not found: {checkpoint_dir}")
                sys.exit(1)

            success = uploader.upload_checkpoint(checkpoint_dir, repo_id)
            if success:
                logger.info(f"Successfully uploaded {args.checkpoint}")
            else:
                logger.error(f"Failed to upload {args.checkpoint}")
                sys.exit(1)

        else:
            # Upload all models (GGUF + checkpoints)
            results = uploader.upload_all_models(args.models_dir, args.gguf_path, repo_id, args.private)

            # Print summary
            logger.info("Upload completed:")

            # GGUF results
            if results['gguf']['success']:
                logger.info(f"  ✓ GGUF model: {args.gguf_path.name}")
            elif results['gguf']['failed']:
                logger.error(f"  ✗ GGUF model: {args.gguf_path.name}")

            # Checkpoint results
            logger.info(f"  Successful checkpoints: {len(results['checkpoints']['success'])}")
            for checkpoint in results['checkpoints']['success']:
                logger.info(f"    ✓ {checkpoint}")

            logger.info(f"  Failed checkpoints: {len(results['checkpoints']['failed'])}")
            for checkpoint in results['checkpoints']['failed']:
                logger.error(f"    ✗ {checkpoint}")

            if results['gguf']['failed'] or results['checkpoints']['failed']:
                sys.exit(1)

        logger.info(f"All uploads completed successfully! Repository: https://huggingface.co/{repo_id}")

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        sys.exit(1)


if __name__ == '__main__':
    main()