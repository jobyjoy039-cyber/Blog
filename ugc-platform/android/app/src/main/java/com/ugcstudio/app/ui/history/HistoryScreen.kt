package com.ugcstudio.app.ui.history

import androidx.compose.foundation.clickable
import androidx.compose.foundation.layout.Arrangement
import androidx.compose.foundation.layout.Column
import androidx.compose.foundation.layout.PaddingValues
import androidx.compose.foundation.layout.Row
import androidx.compose.foundation.layout.fillMaxSize
import androidx.compose.foundation.layout.fillMaxWidth
import androidx.compose.foundation.layout.padding
import androidx.compose.foundation.layout.size
import androidx.compose.foundation.lazy.LazyColumn
import androidx.compose.foundation.lazy.items
import androidx.compose.foundation.shape.RoundedCornerShape
import androidx.compose.material3.Card
import androidx.compose.material3.ExperimentalMaterial3Api
import androidx.compose.material3.MaterialTheme
import androidx.compose.material3.Text
import androidx.compose.material3.pulltorefresh.PullToRefreshBox
import androidx.compose.runtime.Composable
import androidx.compose.runtime.getValue
import androidx.compose.ui.Alignment
import androidx.compose.ui.Modifier
import androidx.compose.ui.draw.clip
import androidx.compose.ui.layout.ContentScale
import androidx.compose.ui.unit.dp
import androidx.hilt.navigation.compose.hiltViewModel
import androidx.lifecycle.compose.collectAsStateWithLifecycle
import coil.compose.AsyncImage
import com.ugcstudio.app.domain.model.JobStatus
import java.text.DateFormat
import java.util.Date

@OptIn(ExperimentalMaterial3Api::class)
@Composable
fun HistoryScreen(onOpen: (String) -> Unit, vm: HistoryViewModel = hiltViewModel()) {
    val state by vm.state.collectAsStateWithLifecycle()
    PullToRefreshBox(isRefreshing = state.loading, onRefresh = vm::refresh, modifier = Modifier.fillMaxSize()) {
        LazyColumn(contentPadding = PaddingValues(16.dp), verticalArrangement = Arrangement.spacedBy(12.dp)) {
            item { Text("Library", style = MaterialTheme.typography.headlineMedium) }
            state.error?.let { item { Text(it, color = MaterialTheme.colorScheme.error) } }
            if (state.jobs.isEmpty() && !state.loading && state.error == null) {
                item { Text("No ads yet. Create one from the first tab.") }
            }
            items(state.jobs, key = { it.id }) { job ->
                Card(Modifier.fillMaxWidth().clickable { onOpen(job.id) }) {
                    Row(Modifier.padding(12.dp), verticalAlignment = Alignment.CenterVertically) {
                        if (job.status == JobStatus.SUCCEEDED) {
                            AsyncImage(vm.thumbnailUrl(job.id), null,
                                Modifier.size(56.dp, 72.dp).clip(RoundedCornerShape(8.dp)), contentScale = ContentScale.Crop)
                        }
                        Column(Modifier.padding(start = 12.dp)) {
                            Text(job.productTitle ?: "Untitled product", style = MaterialTheme.typography.titleSmall, maxLines = 1)
                            Text("${job.platform.label} · ${job.framework} · ${job.status.name.lowercase()}",
                                style = MaterialTheme.typography.bodySmall, color = MaterialTheme.colorScheme.onSurfaceVariant)
                            Text(DateFormat.getDateTimeInstance(DateFormat.MEDIUM, DateFormat.SHORT).format(Date(job.createdAt)),
                                style = MaterialTheme.typography.labelSmall)
                        }
                    }
                }
            }
        }
    }
}
