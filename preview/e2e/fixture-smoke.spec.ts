import { expect, test } from '@playwright/test';

test.describe('fixture mode smoke test', () => {
  test('loads the Briefing with fixture data and makes no external requests', async ({
    page,
  }) => {
    const externalRequests: string[] = [];
    page.on('request', (request) => {
      const url = request.url();
      if (
        !url.startsWith('http://127.0.0.1:4174') &&
        !url.startsWith('https://fonts.googleapis.com') &&
        !url.startsWith('https://fonts.gstatic.com') &&
        !url.startsWith('data:') &&
        !url.startsWith('blob:')
      ) {
        externalRequests.push(url);
      }
    });

    await page.clock.setFixedTime(new Date('2026-07-29T15:30:00.000Z'));
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    expect(externalRequests).toEqual([]);

    const briefing = page.getByRole('heading', { name: /Good/i });
    await expect(briefing).toBeVisible({ timeout: 10000 });

    await expect(
      page.getByRole('heading', { name: 'Today' }),
    ).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'Needs you' }),
    ).toBeVisible();
    await expect(
      page.getByRole('heading', { name: 'In motion' }),
    ).toBeVisible();
  });

  test('confirmation dialog blocks consequential actions in fixture mode', async ({
    page,
  }) => {
    await page.clock.setFixedTime(new Date('2026-07-29T15:30:00.000Z'));
    await page.goto('/');
    await page.waitForLoadState('networkidle');

    const reviewButton = page.getByRole('button', { name: 'Review and send' });
    await expect(reviewButton).toBeVisible({ timeout: 10000 });

    await reviewButton.click();

    const confirmDialog = page.getByRole('dialog', { name: /Confirm/i });
    await expect(confirmDialog).toBeVisible();

    const cancelButton = confirmDialog.getByRole('button', { name: 'Cancel' });
    await cancelButton.click();
    await expect(confirmDialog).not.toBeVisible();
  });
});
