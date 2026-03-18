package com.budbridge

import android.content.Intent
import android.service.quicksettings.TileService

/**
 * Quick Settings tile — pull down the notification shade and tap
 * the BudBridge tile to claim audio to the phone.
 */
class ClaimTile : TileService() {
    override fun onClick() {
        val intent = Intent(this, BudBridgeService::class.java).apply {
            action = BudBridgeService.ACTION_CLAIM
        }
        startForegroundService(intent)
    }
}
