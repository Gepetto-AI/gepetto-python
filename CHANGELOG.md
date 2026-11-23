# Changelog

## 0.2.0

- Videos: `camera_move()` (0.80 €) and `transition()` (1.60 €), `list_transitions()`. Live keys only; they wait up to 30 minutes, or return at once with `webhook`.

## 0.1.1

- Support email: contact@gepettoapp.com.

## 0.1.0

- Every tool of the Gepetto API v2: enhance, declutter, furnish, sunshine, creative_redesign, surfaces, upscale.
- Waits for the image; retries with the same idempotency key; follows the job if the connection drops.
- `GepettoError` with `code`, `param`, `status`, `job_id`.
- Lists, jobs, account, usage. `verify_webhook()`. `mask_from_file()`.
