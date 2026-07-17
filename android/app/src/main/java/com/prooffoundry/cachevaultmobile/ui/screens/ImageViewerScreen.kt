package com.prooffoundry.cachevaultmobile.ui.screens

import android.graphics.BitmapFactory
import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.gestures.awaitEachGesture
import androidx.compose.foundation.gestures.awaitFirstDown
import androidx.compose.foundation.gestures.calculatePan
import androidx.compose.foundation.gestures.calculateZoom
import androidx.compose.foundation.ExperimentalFoundationApi
import androidx.compose.foundation.gestures.detectTapGestures
import androidx.compose.foundation.horizontalScroll
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.pager.HorizontalPager
import androidx.compose.foundation.pager.rememberPagerState
import androidx.compose.foundation.rememberScrollState
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material3.Button
import androidx.compose.material3.CircularProgressIndicator
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.material3.TopAppBarDefaults
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableFloatStateOf
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.runtime.snapshotFlow
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.geometry.Offset
import androidx.compose.ui.graphics.Color
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.graphics.graphicsLayer
import androidx.compose.ui.input.pointer.PointerInputScope
import androidx.compose.ui.input.pointer.pointerInput
import androidx.compose.ui.input.pointer.positionChanged
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.layout.onSizeChanged
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.res.stringResource
import androidx.compose.ui.unit.IntSize
import androidx.compose.ui.unit.dp
import com.prooffoundry.cachevaultmobile.R
import com.prooffoundry.cachevaultmobile.data.ClipSummary
import com.prooffoundry.cachevaultmobile.data.ImageAssetState
import com.prooffoundry.cachevaultmobile.data.ImageFileHelper
import com.prooffoundry.cachevaultmobile.ui.ClipListFormatter

private const val MIN_SCALE = 1f
private const val MAX_SCALE = 5f
private const val DOUBLE_TAP_SCALE = 2.5f

/**
 * Full-screen viewer for a screenshot gallery: pinch/pan/double-tap zoom on the current image,
 * and — only while at 1x zoom — horizontal swipe to the previous/next image in [gallery].
 */
@OptIn(ExperimentalMaterial3Api::class, ExperimentalFoundationApi::class)
@Composable
fun ImageViewerScreen(
    gallery: List<ClipSummary>,
    currentIndex: Int,
    currentAsset: ImageAssetState,
    neighborAssets: Map<String, ImageAssetState>,
    onIndexChanged: (Int) -> Unit,
    onBack: () -> Unit,
    onRetry: (() -> Unit)?,
    onShare: () -> Unit,
    onSave: () -> Unit,
) {
    if (gallery.isEmpty()) return
    val context = LocalContext.current
    val safeIndex = currentIndex.coerceIn(0, gallery.lastIndex)
    val pagerState = rememberPagerState(initialPage = safeIndex) { gallery.size }

    var scale by remember { mutableFloatStateOf(MIN_SCALE) }
    var offset by remember { mutableStateOf(Offset.Zero) }
    var containerSize by remember { mutableStateOf(IntSize.Zero) }

    LaunchedEffect(pagerState) {
        snapshotFlow { pagerState.currentPage }.collect { page ->
            scale = MIN_SCALE
            offset = Offset.Zero
            onIndexChanged(page)
        }
    }

    fun clampOffset(rawOffset: Offset, currentScale: Float): Offset {
        if (containerSize == IntSize.Zero || currentScale <= MIN_SCALE) return Offset.Zero
        val maxX = (containerSize.width * (currentScale - 1f)) / 2f
        val maxY = (containerSize.height * (currentScale - 1f)) / 2f
        return Offset(
            rawOffset.x.coerceIn(-maxX, maxX),
            rawOffset.y.coerceIn(-maxY, maxY),
        )
    }

    val currentClip = gallery[pagerState.currentPage.coerceIn(0, gallery.lastIndex)]
    val currentBitmap = remember(currentAsset.bytes) {
        currentAsset.bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
    }

    Scaffold(
        containerColor = Color.Black,
        topBar = {
            TopAppBar(
                title = {
                    Column {
                        Text(
                            ClipListFormatter.imageTitle(currentClip),
                            color = Color.White,
                            style = MaterialTheme.typography.titleSmall,
                            maxLines = 1,
                        )
                        Text(
                            "${pagerState.currentPage + 1} of ${gallery.size}",
                            color = Color.White.copy(alpha = 0.7f),
                            style = MaterialTheme.typography.labelSmall,
                        )
                    }
                },
                navigationIcon = {
                    IconButton(onClick = onBack) {
                        Icon(
                            Icons.AutoMirrored.Filled.ArrowBack,
                            contentDescription = stringResource(R.string.image_viewer_back),
                            tint = Color.White,
                        )
                    }
                },
                colors = TopAppBarDefaults.topAppBarColors(containerColor = Color.Black),
            )
        },
    ) { padding ->
        Column(
            modifier = Modifier
                .fillMaxSize()
                .padding(padding)
                .background(Color.Black),
        ) {
            HorizontalPager(
                state = pagerState,
                userScrollEnabled = scale <= MIN_SCALE,
                beyondBoundsPageCount = 1,
                modifier = Modifier
                    .weight(1f)
                    .fillMaxWidth(),
            ) { page ->
                val isCurrent = page == pagerState.currentPage
                val clip = gallery[page]
                val asset = if (isCurrent) {
                    currentAsset
                } else {
                    neighborAssets[clip.id] ?: ImageAssetState(loading = clip.hasAsset)
                }
                val bitmap = if (isCurrent) {
                    currentBitmap
                } else {
                    remember(asset.bytes) {
                        asset.bytes?.let { BitmapFactory.decodeByteArray(it, 0, it.size)?.asImageBitmap() }
                    }
                }

                Box(
                    modifier = Modifier.fillMaxSize(),
                    contentAlignment = Alignment.Center,
                ) {
                    when {
                        asset.loading -> CircularProgressIndicator(color = Color.White)
                        bitmap != null -> {
                            Image(
                                bitmap = bitmap,
                                contentDescription = clip.preview,
                                contentScale = ContentScale.Fit,
                                modifier = Modifier
                                    .fillMaxSize()
                                    .onSizeChanged { if (isCurrent) containerSize = it }
                                    .graphicsLayer(
                                        scaleX = if (isCurrent) scale else MIN_SCALE,
                                        scaleY = if (isCurrent) scale else MIN_SCALE,
                                        translationX = if (isCurrent) offset.x else 0f,
                                        translationY = if (isCurrent) offset.y else 0f,
                                    )
                                    .pointerInput(Unit) {
                                        detectZoomAndPageAwarePan(
                                            canPan = { scale > MIN_SCALE },
                                        ) { pan, zoom ->
                                            val newScale = (scale * zoom).coerceIn(MIN_SCALE, MAX_SCALE)
                                            val panned = if (newScale > MIN_SCALE) offset + pan else Offset.Zero
                                            scale = newScale
                                            offset = clampOffset(panned, newScale)
                                        }
                                    }
                                    .pointerInput(Unit) {
                                        detectTapGestures(
                                            onDoubleTap = {
                                                if (scale > MIN_SCALE) {
                                                    scale = MIN_SCALE
                                                    offset = Offset.Zero
                                                } else {
                                                    scale = DOUBLE_TAP_SCALE
                                                }
                                            },
                                        )
                                    },
                            )
                        }
                        asset.error != null -> ViewerMessage(asset.error, if (isCurrent) onRetry else null)
                        !clip.hasAsset -> ViewerMessage(
                            stringResource(R.string.image_asset_placeholder),
                            null,
                        )
                    }
                }
            }
            if (currentBitmap != null) {
                Row(
                    modifier = Modifier
                        .fillMaxWidth()
                        .horizontalScroll(rememberScrollState())
                        .padding(horizontal = 16.dp, vertical = 12.dp),
                    horizontalArrangement = Arrangement.spacedBy(12.dp),
                ) {
                    OutlinedButton(onClick = {
                        currentAsset.bytes?.let {
                            ImageFileHelper.shareImage(context, it, currentAsset.contentType, currentClip.id)
                            onShare()
                        }
                    }) { Text("Share", maxLines = 1) }
                    OutlinedButton(onClick = {
                        currentAsset.bytes?.let {
                            val ok = ImageFileHelper.saveToPictures(
                                context, it, currentAsset.contentType, "cachevault_${currentClip.id}.png",
                            )
                            onSave()
                            android.widget.Toast.makeText(
                                context,
                                if (ok) "Saved to Pictures/CacheVault" else "Could not save image",
                                android.widget.Toast.LENGTH_LONG,
                            ).show()
                        }
                    }) { Text("Save to Phone", maxLines = 1) }
                    OutlinedButton(onClick = {
                        currentAsset.bytes?.let {
                            ImageFileHelper.openInOtherApp(context, it, currentAsset.contentType, currentClip.id)
                        }
                    }) { Text(stringResource(R.string.open_in_other_app), maxLines = 1) }
                }
            }
        }
    }
}

/**
 * Like [androidx.compose.foundation.gestures.detectTransformGestures], but a single-finger drag
 * is only consumed (and reported as pan) when [canPan] is true — otherwise the touch is left
 * unconsumed so an enclosing [HorizontalPager] can treat it as a page swipe. Multi-finger pinch
 * is always handled, regardless of [canPan], so zooming in from 1x still works.
 */
private suspend fun PointerInputScope.detectZoomAndPageAwarePan(
    canPan: () -> Boolean,
    onGesture: (pan: Offset, zoom: Float) -> Unit,
) {
    awaitEachGesture {
        awaitFirstDown(requireUnconsumed = false)
        do {
            val event = awaitPointerEvent()
            val zoomChange = event.calculateZoom()
            val panChange = event.calculatePan()
            val multiTouch = event.changes.size > 1
            if (multiTouch || canPan()) {
                if (zoomChange != 1f || panChange != Offset.Zero) {
                    onGesture(panChange, zoomChange)
                }
                event.changes.forEach { change ->
                    if (change.positionChanged()) change.consume()
                }
            }
        } while (event.changes.any { it.pressed })
    }
}

@Composable
private fun ViewerMessage(message: String, onRetry: (() -> Unit)?) {
    Column(
        horizontalAlignment = Alignment.CenterHorizontally,
        verticalArrangement = Arrangement.spacedBy(12.dp),
        modifier = Modifier.padding(24.dp),
    ) {
        Text(message, style = MaterialTheme.typography.bodyMedium, color = Color.White)
        if (onRetry != null) {
            Button(onClick = onRetry) { Text(stringResource(R.string.image_viewer_retry)) }
        }
    }
}
