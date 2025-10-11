# Browser PDF Generator - Setup Guide

This guide will help you set up the browser-based PDF generator for GitHub Pages.

## Quick Start (Local Testing)

1. **Update the configuration** in `card_generator.html`:
   ```javascript
   // Line ~138
   const GITHUB_USER = 'your-username';  // Replace with your GitHub username
   ```

2. **Test locally**:
   - Open `card_generator.html` in your browser
   - If images don't load locally, proceed to GitHub Pages setup

## GitHub Pages Deployment

### Step 1: Update Configuration

Edit `card_generator.html` and find these lines:
```javascript
const GITHUB_USER = 'your-username';  // UPDATE THIS
const GITHUB_REPO = 'moonsimdata';
const GITHUB_BRANCH = 'main';
```

Replace `'your-username'` with your actual GitHub username.

### Step 2: Commit and Push

```bash
cd character_wide_cards
git add card_generator.html
git commit -m "Add browser-based PDF generator"
git push origin main
```

### Step 3: Enable GitHub Pages

1. Go to your repository on GitHub
2. Click **Settings** (top right)
3. Scroll down to **Pages** section (left sidebar)
4. Under **Source**, select:
   - Branch: `main`
   - Folder: `/ (root)`
5. Click **Save**
6. Wait 1-2 minutes for deployment

### Step 4: Access Your Generator

Your generator will be available at:
```
https://[your-username].github.io/moonsimdata/character_wide_cards/card_generator.html
```

Replace `[your-username]` with your GitHub username.

## Troubleshooting

### Images Don't Load

**Problem**: Characters load but images show errors

**Solutions**:
1. Verify `GITHUB_USER` is set correctly in the HTML file
2. Check that images exist in `generated_wide_cards_with_left_text/`
3. Ensure your repository is **public** (GitHub Pages requires this for raw URLs)
4. Check browser console (F12) for specific error messages

### Character Data Doesn't Load

**Problem**: "Failed to load character data" error

**Solutions**:
1. Verify `moonstone_data.json` exists in `character_wide_cards/`
2. Check that JSON is valid (no syntax errors)
3. Ensure repository is public
4. Try accessing the raw JSON URL directly in browser:
   ```
   https://raw.githubusercontent.com/[user]/moonsimdata/main/character_wide_cards/moonstone_data.json
   ```

### CORS Errors

**Problem**: Cross-Origin Request Blocked errors

**Solution**: 
- Use GitHub Pages (not local file://)
- GitHub's raw.githubusercontent.com properly handles CORS

### PDF Generation Fails

**Problem**: PDFs don't generate or are blank

**Solutions**:
1. Ensure at least one character is selected
2. Ensure at least one format checkbox is checked
3. Wait for all images to load (check browser console)
4. Try with fewer characters first
5. Clear browser cache and reload

## Usage Instructions

### Selecting Characters

1. **Search**: Type in search box to filter by name
2. **Filter**: Use dropdown to filter by faction
3. **Select**: Click character cards to toggle selection
4. **Bulk Actions**: Use "Select All" or "Deselect All" buttons

### Generating PDFs

1. Select desired characters (at least one)
2. Choose format(s):
   - **Landscape 2x2 Tarot** (recommended for printing)
   - **Portrait 1x2 Scaled** (alternative layout)
   - **Native Pixel Size** (full resolution, 1 per page)
3. Click **Preview** to see first page (optional)
4. Click **Generate PDFs** to download

Multiple formats selected = multiple PDF files downloaded.

### Print Settings

For best results when printing:
- Use **Landscape 2x2 Tarot** format
- Print at 100% scale (no scaling)
- Use high-quality/best print settings
- Cards are sized at 120mm x 70mm (tarot size)

## Features

- ✅ No installation required
- ✅ Works on desktop and mobile browsers
- ✅ Filter by name or faction
- ✅ Select only characters you want
- ✅ Preview before generating
- ✅ Multiple format support
- ✅ Images cached for faster subsequent generation
- ✅ Matches Python script output exactly

## Browser Compatibility

Tested and working on:
- Chrome/Edge (recommended)
- Firefox
- Safari
- Mobile browsers

## Technical Notes

### Image URLs
Images are loaded from:
```
https://raw.githubusercontent.com/[user]/[repo]/[branch]/character_wide_cards/generated_wide_cards_with_left_text/[CharacterName]_wide_card_with_text.png
```

### Libraries Used
- **Bootstrap 5.3.0** - UI framework
- **Bootstrap Icons 1.10.0** - Icons
- **jsPDF 2.5.1** - PDF generation

All loaded from CDN, no local dependencies needed.

### Security
- No data sent to external servers
- All processing happens in your browser
- No cookies or tracking
- No server-side code

## Updating Character Data

After generating new character cards with Python scripts:

1. Commit and push updated images and JSON:
   ```bash
   git add generated_wide_cards_with_left_text/*.png
   git add moonstone_data.json
   git commit -m "Update character cards"
   git push origin main
   ```

2. Clear browser cache or hard refresh (Ctrl+Shift+R / Cmd+Shift+R)

3. Characters will automatically update in the generator

## Support

If you encounter issues:
1. Check browser console (F12) for error messages
2. Verify all setup steps completed
3. Test with a single character first
4. Ensure repository is public
5. Check that GitHub Pages is enabled and deployed

---

**Need help?** Open an issue on the GitHub repository.

