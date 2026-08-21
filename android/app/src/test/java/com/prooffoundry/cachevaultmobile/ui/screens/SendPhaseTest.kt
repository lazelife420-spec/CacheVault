package com.prooffoundry.cachevaultmobile.ui.screens

import org.junit.Assert.assertFalse
import org.junit.Assert.assertTrue
import org.junit.Test

/**
 * Guards the send-tap invariant.
 *
 * Repeated taps on the share screen previously produced several identical vault
 * items on the desktop from a single user intent, because nothing prevented a
 * second send while the first was still running.
 */
class SendPhaseTest {

    @Test
    fun idleAllowsASend() {
        assertFalse(SendPhase.IDLE.blocksNewSend())
    }

    @Test
    fun inFlightSendBlocksAnotherSend() {
        assertTrue(SendPhase.SENDING.blocksNewSend())
    }

    @Test
    fun completedSendBlocksAnotherSend() {
        assertTrue(SendPhase.SENT.blocksNewSend())
    }

    @Test
    fun failedSendStaysRetryable() {
        assertFalse(SendPhase.FAILED.blocksNewSend())
    }

    @Test
    fun repeatedTapsDuringOneRequestYieldExactlyOneSend() {
        var phase = SendPhase.IDLE
        var sendsStarted = 0

        // Simulate the tap handler: four rapid taps while the request is running,
        // which is what produced four duplicate clips on the desktop.
        repeat(4) {
            if (!phase.blocksNewSend()) {
                sendsStarted++
                phase = SendPhase.SENDING
            }
        }

        assertTrue(sendsStarted == 1)
    }

    @Test
    fun tapsAfterSuccessDoNotStartAnotherSend() {
        var phase = SendPhase.SENT
        var sendsStarted = 0

        repeat(3) {
            if (!phase.blocksNewSend()) {
                sendsStarted++
                phase = SendPhase.SENDING
            }
        }

        assertTrue(sendsStarted == 0)
    }

    @Test
    fun tapAfterFailureStartsExactlyOneRetry() {
        var phase = SendPhase.FAILED
        var sendsStarted = 0

        repeat(3) {
            if (!phase.blocksNewSend()) {
                sendsStarted++
                phase = SendPhase.SENDING
            }
        }

        assertTrue(sendsStarted == 1)
    }
}
