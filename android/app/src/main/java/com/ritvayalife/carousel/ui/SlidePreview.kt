package com.ritvayalife.carousel.ui

import androidx.compose.foundation.Image
import androidx.compose.foundation.background
import androidx.compose.foundation.layout.Box
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.runtime.Composable
import androidx.compose.runtime.LaunchedEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.mutableStateOf
import androidx.compose.runtime.remember
import androidx.compose.runtime.setValue
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.graphics.ImageBitmap
import androidx.compose.ui.graphics.asImageBitmap
import androidx.compose.ui.unit.dp
import com.ritvayalife.carousel.Carousel
import com.ritvayalife.carousel.SlideRenderer
import kotlinx.coroutines.Dispatchers
import kotlinx.coroutines.delay
import kotlinx.coroutines.withContext

/** Renders one slide off the main thread; keeps the old image until the new one is ready. */
@Composable
fun SlidePreview(
    carousel: Carousel,
    index: Int,
    renderer: SlideRenderer,
    modifier: Modifier = Modifier,
    scale: Float = 1f,
) {
    var image by remember { mutableStateOf<ImageBitmap?>(null) }
    val slide = carousel.slides.getOrNull(index)
    LaunchedEffect(slide, carousel.label, carousel.slides.size, index, scale) {
        if (image != null) delay(150) // debounce while typing
        image = withContext(Dispatchers.Default) { renderer.render(carousel, index, scale).asImageBitmap() }
    }
    Box(
        modifier
            .aspectRatio(4f / 5f)
            .clip(RoundedCornerShape(8.dp))
            .background(Cream),
    ) {
        image?.let { Image(bitmap = it, contentDescription = "Slide ${index + 1}", modifier = Modifier.fillMaxSize()) }
    }
}
