package com.budbridge

import android.app.PendingIntent
import android.appwidget.AppWidgetManager
import android.appwidget.AppWidgetProvider
import android.content.Context
import android.content.Intent
import android.widget.RemoteViews

/**
 * Home screen widget — one tap to claim audio to the phone.
 */
class ClaimWidget : AppWidgetProvider() {

    override fun onUpdate(
        context: Context,
        appWidgetManager: AppWidgetManager,
        appWidgetIds: IntArray
    ) {
        for (id in appWidgetIds) {
            val views = RemoteViews(context.packageName, R.layout.widget_claim)
            views.setOnClickPendingIntent(R.id.widget_button, buildClaimIntent(context))
            appWidgetManager.updateAppWidget(id, views)
        }
    }

    private fun buildClaimIntent(context: Context): PendingIntent {
        val serviceIntent = Intent(context, BudBridgeService::class.java).apply {
            action = BudBridgeService.ACTION_CLAIM
        }
        return PendingIntent.getService(
            context, 0, serviceIntent,
            PendingIntent.FLAG_UPDATE_CURRENT or PendingIntent.FLAG_IMMUTABLE
        )
    }
}
