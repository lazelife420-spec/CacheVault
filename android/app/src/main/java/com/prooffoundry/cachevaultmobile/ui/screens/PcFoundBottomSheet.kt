package com.prooffoundry.cachevaultmobile.ui.screens

import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.material3.Button
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.ModalBottomSheet
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Text
import androidx.compose.material3.TextButton
import androidx.compose.material3.rememberModalBottomSheetState
import androidx.compose.runtime.Composable
import androidx.compose.ui.Modifier
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.connect.PcFoundOffer
import com.prooffoundry.cachevaultmobile.connect.PcOfferMode

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun PcFoundBottomSheet(
    offer: PcFoundOffer,
    loading: Boolean,
    onConnect: () -> Unit,
    onPairNewDevice: () -> Unit,
    onManualSetup: () -> Unit,
    onDismiss: () -> Unit,
) {
    val sheetState = rememberModalBottomSheetState(skipPartiallyExpanded = true)
    ModalBottomSheet(
        onDismissRequest = onDismiss,
        sheetState = sheetState,
    ) {
        Column(
            modifier = Modifier
                .fillMaxWidth()
                .padding(horizontal = 24.dp, vertical = 8.dp),
            verticalArrangement = Arrangement.spacedBy(12.dp),
        ) {
            Text(
                stringResource(R.string.pc_found_title),
                style = MaterialTheme.typography.titleLarge,
            )
            Text(
                "${offer.displayName}\n${offer.host}:${offer.port}",
                style = MaterialTheme.typography.bodyLarge,
            )
            Text(
                when (offer.mode) {
                    PcOfferMode.PAIRED_TRY_CONNECT ->
                        stringResource(R.string.pc_found_secure_local)
                    PcOfferMode.REPAIR_NEEDED ->
                        stringResource(R.string.repair_needed_body)
                    PcOfferMode.NO_TOKEN ->
                        stringResource(R.string.pc_found_pair_body)
                },
                style = MaterialTheme.typography.bodyMedium,
                color = MaterialTheme.colorScheme.onSurfaceVariant,
            )
            when (offer.mode) {
                PcOfferMode.PAIRED_TRY_CONNECT -> {
                    Button(
                        onClick = onConnect,
                        enabled = !loading,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(if (loading) "Connecting…" else stringResource(R.string.connect))
                    }
                    OutlinedButton(
                        onClick = onPairNewDevice,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.pair_new_device))
                    }
                }
                PcOfferMode.REPAIR_NEEDED -> {
                    Button(
                        onClick = onPairNewDevice,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.repair_pair))
                    }
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.disconnect))
                    }
                }
                PcOfferMode.NO_TOKEN -> {
                    Button(
                        onClick = onPairNewDevice,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.pair_this_phone))
                    }
                    OutlinedButton(
                        onClick = onDismiss,
                        modifier = Modifier.fillMaxWidth(),
                    ) {
                        Text(stringResource(R.string.not_mine))
                    }
                }
            }
            TextButton(onClick = onManualSetup, modifier = Modifier.fillMaxWidth()) {
                Text(stringResource(R.string.manual_setup))
            }
        }
    }
}
