# Smooth Provider Refresh Animation Design

## Goal

Make the provider-logo refresh animation visibly smoother by rendering it at approximately 30 frames per second without changing the timing of the widget's other animations.

## Design

Keep the existing 200 ms general animation timer for status dots, waiting pulses, the startup logo, and the LIVE badge. Move provider-logo rotation to a dedicated 33 ms timer that runs only while a usage refresh is active.

Starting a refresh records the selected providers and starts the dedicated timer if it is not already running. Each tick advances the logo angle at a speed equivalent to the current rotation and redraws only the selected provider logos. The angle calculation must account for the shorter interval so the animation becomes smoother without becoming substantially faster.

When the refresh succeeds or fails, stop the dedicated timer, clear the active provider set, reset affected logos to their upright angle, and redraw them. Automatic refresh continues to animate both providers, while a manual logo click animates only the selected provider.

## Failure and Lifecycle Handling

The timer must have at most one active GLib source. Cleanup occurs on both successful and failed refresh completion. A late timer callback after cleanup should return without restarting the animation or changing provider state.

## Verification

Add focused tests or a GTK smoke check covering the 33 ms interval, single-timer behavior, provider-specific redraws, and cleanup/reset after completion. Run Python compilation, the unit-test suite, and the existing widget demo or logo smoke check.
