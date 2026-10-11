package com.ugcstudio.app.ui.job

import android.content.Intent
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.aspectRatio
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.rememberScrollState
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.foundation.verticalScroll
import androidx.compose.material.icons.Icons
import androidx.compose.material.icons.automirrored.filled.ArrowBack
import androidx.compose.material.icons.filled.CheckCircle
import androidx.compose.material.icons.filled.ErrorOutline
import androidx.compose.material.icons.filled.Refresh
import androidx.compose.material.icons.filled.Share
import androidx.compose.material.icons.filled.WarningAmber
import androidx.compose.material3.Button
import androidx.compose.material3.Card
import androidx.compose.material3.CardDefaults
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.Icon
import androidx.compose.material3.IconButton
import androidx.compose.material3.LinearProgressIndicator
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.OutlinedButton
import androidx.compose.material3.Scaffold
import androidx.compose.material3.Text
import androidx.compose.material3.TopAppBar
import androidx.compose.runtime.Composable
import androidx.compose.runtime.DisposableEffect
import androidx.compose.runtime.getValue
import androidx.compose.runtime.remember
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.platform.LocalContext
import androidx.compose.ui.text.font.FontWeight
import androidx.compose.ui.unit.dp
import androidx.compose.ui.viewinterop.AndroidView
import androidx.core.content.FileProvider
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import androidx.media3.common.MediaItem
import androidx.media3.exoplayer.ExoPlayer
import androidx.media3.ui.PlayerView
import com.ugcstudio.app.domain.model.AdJob
import com.ugcstudio.app.domain.model.JobStatus
import java.io.File

private val STEP_LABELS = mapOf(
    "ingest" to "Reading the product", "analyze" to "Finding the angle", "script" to "Writing the script",
    "voice" to "Recording the voiceover", "render" to "Editing the video",
)

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun JobScreen(onBack: () -> Unit, vm: JobViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    val context = LocalContext.current
    Scaffold(topBar = {
        TopAppBar(
            title = { Text(state.job?.productTitle ?: "Your ad", maxLines = 1) },
            navigationIcon = { IconButton(onClick = onBack) { Icon(Icons.AutoMirrored.Filled.ArrowBack, "Back") } },
        )
    }) { pad ->
        Column(
            Modifier.padding(pad).verticalScroll(rememberScrollState()).padding(16.dp),
            verticalArrangement = Arrangement.spacedBy(16.dp),
        ) {
            val job = state.job
            when {
                job == null -> LinearProgressIndicator(Modifier.fillMaxWidth())
                job.status == JobStatus.FAILED -> FailedCard(job, vm::retry)
                job.status != JobStatus.SUCCEEDED -> ProgressCard(job)
                else -> {
                    val video = state.video
                    if (video != null) VideoPlayer(video, job) else LinearProgressIndicator(Modifier.fillMaxWidth())
                    Row(horizontalArrangement = Arrangement.spacedBy(12.dp)) {
                        Button(onClick = { video?.let { share(context, it, job) } }, enabled = video != null) {
                            Icon(Icons.Default.Share, null); Text("  Share / save")
                        }
                        job.durationSeconds?.let { Text("%.1fs · %s".format(it, job.platform.label), Modifier.align(Alignment.CenterVertically)) }
                    }
                }
            }
            state.error?.let { Text(it, color = MaterialTheme.colorScheme.error) }
            job?.let { ScriptCard(it) }
        }
    }
}

@Composable
private fun ProgressCard(job: AdJob) {
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text(STEP_LABELS[job.step] ?: "Waiting in the queue", style = MaterialTheme.typography.titleMedium)
            LinearProgressIndicator(progress = { job.progress }, modifier = Modifier.fillMaxWidth())
            STEP_LABELS.forEach { (step, label) ->
                val done = job.trace.any { it.step == step || it.step.startsWith("$step[") }
                Row(verticalAlignment = Alignment.CenterVertically) {
                    Icon(Icons.Default.CheckCircle, null, Modifier.size(18.dp),
                        tint = if (done) MaterialTheme.colorScheme.primary else MaterialTheme.colorScheme.outlineVariant)
                    Text("  $label", color = if (done) MaterialTheme.colorScheme.onSurface else MaterialTheme.colorScheme.onSurfaceVariant)
                }
            }
        }
    }
}

@Composable
private fun FailedCard(job: AdJob, retry: () -> Unit) {
    Card(colors = CardDefaults.cardColors(containerColor = MaterialTheme.colorScheme.errorContainer)) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(8.dp)) {
            Row(verticalAlignment = Alignment.CenterVertically) {
                Icon(Icons.Default.ErrorOutline, null); Text("  This ad couldn't be made", fontWeight = FontWeight.Bold)
            }
            Text(job.error ?: "Unknown error", style = MaterialTheme.typography.bodySmall)
            OutlinedButton(onClick = retry) { Icon(Icons.Default.Refresh, null); Text("  Try again") }
        }
    }
}

@Composable
private fun VideoPlayer(file: File, job: AdJob) {
    val context = LocalContext.current
    val player = remember(file) {
        ExoPlayer.Builder(context).build().apply {
            setMediaItem(MediaItem.fromUri(file.toURI().toString())); prepare(); playWhenReady = true
        }
    }
    DisposableEffect(player) { onDispose { player.release() } }
    val ratio = job.platform.aspect.split(":").let { (w, h) -> w.toFloat() / h.toFloat() }
    AndroidView(
        factory = { PlayerView(it).apply { this.player = player } },
        modifier = Modifier.fillMaxWidth(if (ratio < 1f) 0.75f else 1f).aspectRatio(ratio).clip(RoundedCornerShape(16.dp)),
    )
}

@Composable
private fun ScriptCard(job: AdJob) {
    if (job.scenes.isEmpty()) return
    Card(Modifier.fillMaxWidth()) {
        Column(Modifier.padding(16.dp), verticalArrangement = Arrangement.spacedBy(10.dp)) {
            Text("Script · ${job.framework}", style = MaterialTheme.typography.titleMedium)
            job.scenes.forEach { s ->
                Column {
                    Text(s.kind.uppercase(), style = MaterialTheme.typography.labelSmall, color = MaterialTheme.colorScheme.primary)
                    Text(s.voice)
                }
            }
            if (job.caption.isNotBlank()) {
                Text("Caption", style = MaterialTheme.typography.labelLarge)
                Text("${job.caption}\n${job.hashtags.joinToString(" ")}", style = MaterialTheme.typography.bodySmall)
            }
            job.claimWarnings.forEach {
                Row { Icon(Icons.Default.WarningAmber, null, Modifier.size(16.dp), tint = MaterialTheme.colorScheme.error); Text("  $it", style = MaterialTheme.typography.bodySmall) }
            }
        }
    }
}

private fun share(context: android.content.Context, file: File, job: AdJob) {
    val uri = FileProvider.getUriForFile(context, "${context.packageName}.files", file)
    val intent = Intent(Intent.ACTION_SEND).apply {
        type = "video/mp4"
        putExtra(Intent.EXTRA_STREAM, uri)
        putExtra(Intent.EXTRA_TEXT, "${job.caption}\n${job.hashtags.joinToString(" ")}".trim())
        addFlags(Intent.FLAG_GRANT_READ_URI_PERMISSION)
    }
    context.startActivity(Intent.createChooser(intent, "Share ad"))
}
