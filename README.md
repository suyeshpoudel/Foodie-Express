# Django Online Food
This project is a simple online food ordering app built using Django.


# Requirements
Ensure the following are installed on your computer:
1. Python 3.8+
2. pip(Python package installer)
3. SQLite

# Setup Instructions
1. Clone the repository: `git clone https://github.com/supo21/Django-online-food.git`.
2. Navigate to the project directory: `cd django-online-food`.
3. Create and activate virtual environment: `python -m venv venv` and `.\venv\Scripts\activate`.
4. Install dependencies: `pip install -r requirements.txt`.
5. Navigate to the source code folder: `cd onlinefood`.
6. Setup the database: `python manage.py makemigrations` and `python manage.py migrate`.
7. Start the development server: `python manage.py runserver`.

# Usage
1. Access the application through your browser at `http://127.0.0.1:8000/`.

# Seeding Data
Run these commands from the `onlinefood` directory after `python manage.py migrate`:

1. Create categories and menu items with generated placeholder images:
   `python manage.py seed_items`
2. Replace the placeholders with real food photos from Wikimedia Commons:
   `python manage.py update_item_images`

Both commands are safe to re-run. Existing categories/items are skipped, and images use deterministic filenames.

`update_item_images` options:

- `--item "Paneer"` updates only matching item names.
- `--dry-run` shows the selected source image without downloading.
- `--delay 1.0` sets the wait between API lookups (default: `1.0`).

The command retries transient failures, validates each download with Pillow, and saves a 512x512 JPEG under `MEDIA_ROOT/item/`.

# Deployment Notes
`build.sh` runs `migrate` and `seed_items` automatically. To refresh images on a deployed database, run the command where the application files live (for example, the Render Shell):

```bash
python manage.py update_item_images
```

Image files are written to `MEDIA_ROOT`, not to the database. Two deployment options:

1. Run the command on the deployed server (for example, the Render Shell). Attach a persistent disk if images must survive redeploys, and point `DJANGO_MEDIA_ROOT` at the disk mount.
2. Run the command locally against the deployed database, then deploy the files:

   ```bash
   DATABASE_URL='postgresql://user:password@host:5432/dbname' python manage.py update_item_images
   git add -f onlinefood/public/media/item
   git commit -m "Update item images"
   git push
   ```

   `public/media/` is gitignored, so `-f` is required. Filenames are deterministic, so this stays at one image per item.

If `DJANGO_DEBUG=False`, also configure media file serving, because WhiteNoise only serves collected static files.
