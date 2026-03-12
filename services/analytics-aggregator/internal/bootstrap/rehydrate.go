package bootstrap

import (
	"context"
	"time"

	"analytics-aggregator/internal/flush"
	"analytics-aggregator/internal/state"
)

func Rehydrate(ctx context.Context, writer *flush.Writer, store *state.Store, minutes int) error {
	since := time.Now().UTC().Add(-time.Duration(minutes) * time.Minute)
	rows, err := writer.Rehydrate(ctx, since)
	if err != nil {
		return err
	}
	store.LoadBuckets(rows)
	return nil
}
