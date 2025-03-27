"""Visualization tools for Drive Labels reporting."""

import os
import tempfile
import logging
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional, Any, Union, Tuple

from legal_drive_labels_manager.reporting.statistics import LabelStatistics


class ReportGenerator:
    """Generate visual reports for Drive Labels usage.
    
    This class provides tools for generating comprehensive reports on
    label usage across your Google Drive environment.
    
    Attributes:
        statistics: LabelStatistics instance for gathering data
        _has_visualization_libs: Whether visualization libraries are available
    """

    def __init__(self, statistics: Optional[LabelStatistics] = None) -> None:
        """
        Initialize the report generator.
        
        Args:
            statistics: Optional LabelStatistics instance
        """
        self.statistics = statistics or LabelStatistics()
        self._has_visualization_libs = self._check_visualization_libraries()
        self.logger = logging.getLogger(__name__)

    def _check_visualization_libraries(self) -> bool:
        """
        Check if visualization libraries are available.
        
        Returns:
            True if visualization libraries are available, False otherwise
        """
        try:
            import matplotlib
            import pandas
            import seaborn
            return True
        except ImportError:
            return False

    def _ensure_visualization_libraries(self) -> bool:
        """
        Ensure visualization libraries are available or provide installation instructions.
        
        Returns:
            True if libraries are available, False otherwise
        """
        if not self._has_visualization_libs:
            self.logger.warning("Visualization libraries are not installed.")
            print("Visualization libraries are not installed.")
            print("To install required packages:")
            print("pip install pandas matplotlib seaborn")
            return False
        return True

    def generate_usage_report(
        self, 
        output_path: Union[str, Path],
        lookback_days: int = 30,
        top_n_labels: int = 10,
        include_disabled: bool = True
    ) -> bool:
        """
        Generate a comprehensive HTML report on label usage.
        
        Args:
            output_path: Path to save the HTML report
            lookback_days: Number of days to include in activity analysis
            top_n_labels: Number of top labels to highlight
            include_disabled: Whether to include disabled labels in statistics
            
        Returns:
            True if successful, False otherwise
        """
        if not self._ensure_visualization_libraries():
            return False
            
        try:
            import pandas as pd
            import matplotlib.pyplot as plt
            import matplotlib
            import seaborn as sns
            
            # Set non-interactive backend
            matplotlib.use('Agg')
            
            # Set seaborn style
            sns.set_style("whitegrid")
            
            # Get label usage statistics
            usage_stats = self.statistics.count_labels_by_usage()
            
            # Convert to DataFrame for easier manipulation
            df = pd.DataFrame(usage_stats)
            
            # Filter out disabled labels if requested
            if not include_disabled:
                df = df[df['state'] != 'DISABLED']
            
            # Create a temporary directory for figures
            with tempfile.TemporaryDirectory() as temp_dir:
                # Generate figures
                fig_paths = {}
                
                # 1. Bar chart of top labels by usage with improved styling
                top_labels_fig = os.path.join(temp_dir, 'top_labels.png')
                plt.figure(figsize=(12, 7))
                
                # Use top N labels or all if less than N
                top_n = min(top_n_labels, len(df))
                top_df = df.sort_values('file_count', ascending=False).head(top_n)
                
                # Create bar chart with improved styling
                sns.barplot(x='title', y='file_count', data=top_df, palette='Blues_d')
                plt.title('Top Labels by Usage', fontsize=16, pad=20)
                plt.xlabel('Label', fontsize=14)
                plt.ylabel('Number of Files', fontsize=14)
                plt.xticks(rotation=45, ha='right', fontsize=12)
                plt.yticks(fontsize=12)
                
                # Add count labels on top of each bar
                for i, row in enumerate(top_df.itertuples()):
                    plt.text(i, row.file_count + (max(top_df.file_count) * 0.02), 
                             str(row.file_count),
                             ha='center', va='bottom', fontsize=11)
                
                plt.tight_layout()
                plt.savefig(top_labels_fig, dpi=300)
                plt.close()
                
                fig_paths['top_labels'] = top_labels_fig
                
                # 2. Pie chart of label states with improved styling
                if len(df) > 0:  # Only create if there are labels
                    state_counts = df['state'].value_counts()
                    if len(state_counts) > 0:  # Only create if there are states
                        states_fig = os.path.join(temp_dir, 'label_states.png')
                        
                        plt.figure(figsize=(10, 10))
                        colors = sns.color_palette('Blues', len(state_counts))
                        explode = [0.1 if state == 'PUBLISHED' else 0 for state in state_counts.index]
                        
                        # Create pie chart
                        patches, texts, autotexts = plt.pie(
                            state_counts, 
                            labels=state_counts.index, 
                            autopct='%1.1f%%', 
                            startangle=90,
                            explode=explode,
                            colors=colors,
                            shadow=True
                        )
                        
                        # Enhance text appearance
                        for text in texts:
                            text.set_fontsize(14)
                        for autotext in autotexts:
                            autotext.set_fontsize(12)
                            autotext.set_color('white')
                            
                        plt.axis('equal')
                        plt.title('Label States Distribution', fontsize=16, pad=20)
                        plt.savefig(states_fig, dpi=300)
                        plt.close()
                        
                        fig_paths['states'] = states_fig
                
                # 3. Required vs Optional Fields chart
                if len(df) > 0:  # Only create if there are labels
                    fields_fig = os.path.join(temp_dir, 'fields_required.png')
                    
                    # Calculate total fields and required fields
                    total_fields = df['fields'].sum()
                    required_fields = df['required_fields'].sum()
                    optional_fields = total_fields - required_fields
                    
                    if total_fields > 0:  # Only create if there are fields
                        plt.figure(figsize=(10, 8))
                        
                        # Create grouped bar chart
                        field_data = pd.DataFrame({
                            'Category': ['Required Fields', 'Optional Fields'],
                            'Count': [required_fields, optional_fields]
                        })
                        
                        sns.barplot(x='Category', y='Count', data=field_data, palette=['#1f77b4', '#aec7e8'])
                        plt.title('Required vs Optional Fields', fontsize=16, pad=20)
                        plt.xlabel('Field Type', fontsize=14)
                        plt.ylabel('Count', fontsize=14)
                        plt.xticks(fontsize=12)
                        plt.yticks(fontsize=12)
                        
                        # Add count labels on top of each bar
                        for i, count in enumerate(field_data['Count']):
                            plt.text(i, count + (max(field_data['Count']) * 0.02), 
                                    str(count),
                                    ha='center', va='bottom', fontsize=12)
                        
                        # Add percentage labels
                        total = required_fields + optional_fields
                        if total > 0:
                            req_pct = required_fields / total * 100
                            opt_pct = optional_fields / total * 100
                            
                            plt.text(0, required_fields / 2, f"{req_pct:.1f}%", 
                                    ha='center', va='center', fontsize=12, color='white', fontweight='bold')
                            plt.text(1, optional_fields / 2, f"{opt_pct:.1f}%", 
                                    ha='center', va='center', fontsize=12, color='white', fontweight='bold')
                        
                        plt.tight_layout()
                        plt.savefig(fields_fig, dpi=300)
                        plt.close()
                        
                        fig_paths['fields'] = fields_fig
                
                # Get audit log data
                audit_data = self.statistics.analyze_audit_log(days=lookback_days)
                
                # 4. Daily activity chart with improved styling
                if audit_data.get('daily_activity'):
                    daily_df = pd.DataFrame(audit_data['daily_activity'])
                    
                    if len(daily_df) > 0:  # Only create if there's activity data
                        daily_df['date'] = pd.to_datetime(daily_df['date'])
                        daily_df = daily_df.sort_values('date')
                        
                        # Fill in missing dates with zero counts
                        if len(daily_df) > 0:
                            date_range = pd.date_range(
                                start=daily_df['date'].min(),
                                end=daily_df['date'].max()
                            )
                            filled_df = daily_df.set_index('date').reindex(date_range, fill_value=0)
                            filled_df = filled_df.reset_index().rename(columns={'index': 'date'})
                            
                            activity_fig = os.path.join(temp_dir, 'daily_activity.png')
                            plt.figure(figsize=(14, 7))
                            
                            # Plot line chart with area fill
                            sns.lineplot(x='date', y='count', data=filled_df, marker='o', linewidth=2, color='#1f77b4')
                            plt.fill_between(filled_df['date'], filled_df['count'], alpha=0.3, color='#1f77b4')
                            
                            plt.title('Daily Label Activity', fontsize=16, pad=20)
                            plt.xlabel('Date', fontsize=14)
                            plt.ylabel('Number of Actions', fontsize=14)
                            plt.xticks(rotation=45, fontsize=12)
                            plt.yticks(fontsize=12)
                            plt.grid(True, linestyle='--', alpha=0.7)
                            
                            # Add rolling average
                            if len(filled_df) >= 3:  # Only add rolling average if enough data
                                filled_df['rolling_avg'] = filled_df['count'].rolling(window=3, min_periods=1).mean()
                                sns.lineplot(x='date', y='rolling_avg', data=filled_df, 
                                            linestyle='--', linewidth=1.5, color='#ff7f0e', 
                                            label='3-Day Rolling Average')
                                plt.legend(fontsize=12)
                            
                            plt.tight_layout()
                            plt.savefig(activity_fig, dpi=300)
                            plt.close()
                            
                            fig_paths['activity'] = activity_fig
                
                # 5. Action types chart with improved styling
                if audit_data.get('action_types'):
                    action_df = pd.DataFrame(audit_data['action_types'])
                    
                    if len(action_df) > 0:  # Only create if there's action data
                        actions_fig = os.path.join(temp_dir, 'action_types.png')
                        plt.figure(figsize=(12, 8))
                        
                        # Sort by count descending
                        action_df = action_df.sort_values('count', ascending=False)
                        
                        # Create horizontal bar chart
                        bar_colors = sns.color_palette('Blues_r', len(action_df))
                        bars = plt.barh(action_df['type'], action_df['count'], color=bar_colors)
                        
                        plt.title('Actions by Type', fontsize=16, pad=20)
                        plt.xlabel('Count', fontsize=14)
                        plt.ylabel('Action Type', fontsize=14)
                        plt.yticks(fontsize=12)
                        plt.xticks(fontsize=12)
                        
                        # Add count labels
                        for bar in bars:
                            width = bar.get_width()
                            plt.text(width + (max(action_df['count']) * 0.02), 
                                    bar.get_y() + bar.get_height()/2, 
                                    str(int(width)),
                                    va='center', fontsize=12)
                        
                        plt.tight_layout()
                        plt.savefig(actions_fig, dpi=300)
                        plt.close()
                        
                        fig_paths['actions'] = actions_fig
                
                # 6. Users activity chart
                if audit_data.get('users'):
                    users_df = pd.DataFrame(audit_data['users'])
                    
                    if len(users_df) > 0:  # Only create if there's user data
                        # Only take top 10 users
                        top_users = min(10, len(users_df))
                        users_df = users_df.sort_values('count', ascending=False).head(top_users)
                        
                        # Create user activity chart
                        users_fig = os.path.join(temp_dir, 'user_activity.png')
                        plt.figure(figsize=(12, 8))
                        
                        # Create horizontal bar chart
                        user_colors = sns.color_palette('Blues_r', len(users_df))
                        bars = plt.barh(users_df['user'], users_df['count'], color=user_colors)
                        
                        plt.title('Top Users by Activity', fontsize=16, pad=20)
                        plt.xlabel('Number of Actions', fontsize=14)
                        plt.ylabel('User', fontsize=14)
                        plt.yticks(fontsize=12)
                        plt.xticks(fontsize=12)
                        
                        # Add count labels
                        for bar in bars:
                            width = bar.get_width()
                            plt.text(width + (max(users_df['count']) * 0.02), 
                                    bar.get_y() + bar.get_height()/2, 
                                    str(int(width)),
                                    va='center', fontsize=12)
                        
                        plt.tight_layout()
                        plt.savefig(users_fig, dpi=300)
                        plt.close()
                        
                        fig_paths['users'] = users_fig
                
                # Generate HTML report
                html_content = self._generate_html_report(
                    usage_stats, 
                    audit_data, 
                    fig_paths,
                    lookback_days=lookback_days
                )
                
                # Write HTML to file
                with open(output_path, 'w') as f:
                    f.write(html_content)
            
            self.logger.info(f"HTML report generated successfully: {output_path}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error generating report: {e}")
            print(f"Error generating report: {e}")
            return False

    def _generate_html_report(
        self, 
        usage_stats: List[Dict[str, Any]], 
        audit_data: Dict[str, Any],
        figure_paths: Dict[str, str],
        lookback_days: int = 30
    ) -> str:
        """
        Generate HTML content for the report.
        
        Args:
            usage_stats: Label usage statistics
            audit_data: Audit log analysis
            figure_paths: Paths to generated figures
            lookback_days: Number of days included in activity data
            
        Returns:
            HTML content as string
        """
        # Import pandas for HTML table generation
        import pandas as pd
        import base64
        
        # Function to encode images
        def encode_image(image_path):
            if image_path and os.path.exists(image_path):
                with open(image_path, "rb") as image_file:
                    encoded = base64.b64encode(image_file.read()).decode('utf-8')
                    return f"data:image/png;base64,{encoded}"
            return ""
        
        # Convert figures to base64
        figures = {}
        for key, path in figure_paths.items():
            figures[key] = encode_image(path)
        
        # Create DataFrame for tables
        usage_df = pd.DataFrame(usage_stats)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Get user data
        user_data = {}
        try:
            user_data = self.statistics.auth_manager.get_current_user()
        except:
            user_data = {"email": "Unknown", "displayName": "Unknown"}
        
        # Calculate summary statistics
        total_labels = len(usage_stats)
        total_files = sum(item['file_count'] for item in usage_stats) if usage_stats else 0
        published_labels = sum(1 for item in usage_stats if item['state'] == 'PUBLISHED')
        disabled_labels = sum(1 for item in usage_stats if item['state'] == 'DISABLED')
        total_fields = sum(item['fields'] for item in usage_stats) if usage_stats else 0
        required_fields = sum(item['required_fields'] for item in usage_stats) if usage_stats else 0
        avg_fields_per_label = total_fields / total_labels if total_labels > 0 else 0
        
        # Build HTML content
        html = f"""
        <!DOCTYPE html>
        <html lang="en">
        <head>
            <meta charset="UTF-8">
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <title>Drive Labels Usage Report</title>
            <style>
                :root {{
                    --primary-color: #1f77b4;
                    --secondary-color: #aec7e8;
                    --accent-color: #ff7f0e;
                    --text-color: #333;
                    --bg-color: #f8f9fa;
                    --border-color: #ddd;
                }}
                body {{
                    font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
                    line-height: 1.6;
                    color: var(--text-color);
                    max-width: 1200px;
                    margin: 0 auto;
                    padding: 20px;
                    background-color: #f5f7fa;
                }}
                h1, h2, h3 {{
                    color: #2c3e50;
                    margin-top: 1.5em;
                }}
                h1 {{
                    border-bottom: 2px solid var(--primary-color);
                    padding-bottom: 10px;
                }}
                h2 {{
                    border-bottom: 1px solid var(--secondary-color);
                    padding-bottom: 8px;
                }}
                .header {{
                    background-color: white;
                    padding: 30px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .section {{
                    background-color: white;
                    padding: 25px;
                    border-radius: 8px;
                    margin-bottom: 30px;
                    box-shadow: 0 4px 6px rgba(0, 0, 0, 0.1);
                }}
                .summary-stats {{
                    display: grid;
                    grid-template-columns: repeat(auto-fit, minmax(220px, 1fr));
                    gap: 20px;
                    margin: 20px 0;
                }}
                .stat-card {{
                    background-color: #f8f9fa;
                    border-radius: 8px;
                    padding: 15px;
                    text-align: center;
                    border-left: 4px solid var(--primary-color);
                    box-shadow: 0 2px 4px rgba(0, 0, 0, 0.05);
                }}
                .stat-card h3 {{
                    margin-top: 0;
                    margin-bottom: 10px;
                    color: var(--primary-color);
                }}
                .stat-value {{
                    font-size: 28px;
                    font-weight: bold;
                    color: #2c3e50;
                    margin: 10px 0;
                }}
                .stat-description {{
                    font-size: 14px;
                    color: #666;
                }}
                table {{
                    border-collapse: collapse;
                    width: 100%;
                    margin: 20px 0;
                    box-shadow: 0 2px 3px rgba(0, 0, 0, 0.1);
                }}
                th, td {{
                    border: 1px solid var(--border-color);
                    padding: 12px;
                    text-align: left;
                }}
                th {{
                    background-color: var(--primary-color);
                    color: white;
                    font-weight: 600;
                }}
                tr:nth-child(even) {{
                    background-color: #f9f9f9;
                }}
                tr:hover {{
                    background-color: #f1f1f1;
                }}
                .figure {{
                    margin: 25px 0;
                    text-align: center;
                }}
                .figure img {{
                    max-width: 100%;
                    height: auto;
                    border-radius: 8px;
                    box-shadow: 0 4px 8px rgba(0, 0, 0, 0.1);
                }}
                .figure-caption {{
                    font-size: 14px;
                    color: #666;
                    margin-top: 10px;
                }}
                .metadata {{
                    font-size: 14px;
                    color: #666;
                }}
                .insights {{
                    background-color: #eaf4fb;
                    border-left: 4px solid var(--primary-color);
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                .recommendations {{
                    background-color: #fff8e6;
                    border-left: 4px solid var(--accent-color);
                    padding: 15px;
                    margin: 20px 0;
                    border-radius: 4px;
                }}
                footer {{
                    margin-top: 40px;
                    padding-top: 20px;
                    border-top: 1px solid var(--border-color);
                    text-align: center;
                    font-size: 14px;
                    color: #666;
                }}
            </style>
        </head>
        <body>
            <div class="header">
                <h1>Google Drive Labels Usage Report</h1>
                <p class="metadata">
                    Generated on: {timestamp}<br>
                    Generated by: {user_data.get('displayName', 'Unknown')} ({user_data.get('email', 'Unknown')})
                </p>
            </div>
            
            <div class="section">
                <h2>Executive Summary</h2>
                
                <div class="summary-stats">
                    <div class="stat-card">
                        <h3>Total Labels</h3>
                        <div class="stat-value">{total_labels}</div>
                        <div class="stat-description">Drive labels configured</div>
                    </div>
                    <div class="stat-card">
                        <h3>Published Labels</h3>
                        <div class="stat-value">{published_labels}</div>
                        <div class="stat-description">{published_labels/total_labels*100:.1f}% of total labels</div>
                    </div>
                    <div class="stat-card">
                        <h3>Labeled Files</h3>
                        <div class="stat-value">{total_files:,}</div>
                        <div class="stat-description">Files with labels applied</div>
                    </div>
                    <div class="stat-card">
                        <h3>Total Fields</h3>
                        <div class="stat-value">{total_fields}</div>
                        <div class="stat-description">Avg {avg_fields_per_label:.1f} per label</div>
                    </div>
                </div>
                
                <div class="insights">
                    <h3>Key Insights</h3>
                    <p>
                        This report provides an analysis of Google Drive Labels usage across your organization.
                        {f"Based on the last {lookback_days} days of activity, " if audit_data.get('actions_count') else ""}
                        the data shows that {'your organization is actively using Drive Labels to organize and classify content' if total_files > 0 else 'Drive Labels adoption could be improved in your organization'}.
                    </p>
                    <p>
                        {f"The most used label is '{usage_stats[0]['title']}' (applied to {usage_stats[0]['file_count']} files)" if usage_stats else ""}
                        {f" and {published_labels} out of {total_labels} labels are published and available for use." if total_labels > 0 else ""}
                    </p>
                </div>
            </div>
            
            <div class="section">
                <h2>Labels Usage Analysis</h2>
                
                <div class="figure">
                    <h3>Top Labels by Usage</h3>
                    {"<img src=\"" + figures.get('top_labels', '') + "\" alt=\"Top Labels by Usage\">" if 'top_labels' in figures else "<p>No data available for visualization</p>"}
                    <p class="figure-caption">
                        Frequency distribution of labels across files, showing which labels are most commonly applied.
                    </p>
                </div>
                
                <div class="figure">
                    <h3>Label States</h3>
                    {"<img src=\"" + figures.get('states', '') + "\" alt=\"Label States\">" if 'states' in figures else "<p>No data available for visualization</p>"}
                    <p class="figure-caption">
                        Distribution of label states (Published, Draft, Disabled) across your organization.
                    </p>
                </div>
                
                <div class="figure">
                    <h3>Required vs Optional Fields</h3>
                    {"<img src=\"" + figures.get('fields', '') + "\" alt=\"Required vs Optional Fields\">" if 'fields' in figures else "<p>No data available for visualization</p>"}
                    <p class="figure-caption">
                        Breakdown of required and optional fields across all labels.
                    </p>
                </div>
                
                <h3>Label Details</h3>
                {usage_df[['title', 'state', 'file_count', 'fields', 'required_fields']].head(20).to_html(index=False, classes="display") if not usage_df.empty else "<p>No label data available</p>"}
                
                <p class="metadata">Note: Showing top 20 labels only. Total labels: {total_labels}</p>
            </div>
            
            <div class="section">
                <h2>Activity Analysis</h2>
                <p>
                    This section analyzes label-related activity over the past {lookback_days} days,
                    including trends, common actions, and user engagement patterns.
                </p>
                
                <div class="summary-stats">
                    <div class="stat-card">
                        <h3>Total Actions</h3>
                        <div class="stat-value">{audit_data.get('actions_count', 0):,}</div>
                        <div class="stat-description">Label operations performed</div>
                    </div>
                    <div class="stat-card">
                        <h3>Active Users</h3>
                        <div class="stat-value">{len(audit_data.get('users', []))}</div>
                        <div class="stat-description">Users interacting with labels</div>
                    </div>
                    <div class="stat-card">
                        <h3>Peak Day</h3>
                        <div class="stat-value">
                            {max(audit_data.get('daily_activity', [{'date': 'N/A', 'count': 0}]), key=lambda x: x['count'])['date'] if audit_data.get('daily_activity') else 'N/A'}
                        </div>
                        <div class="stat-description">Day with most activity</div>
                    </div>
                    <div class="stat-card">
                        <h3>Most Common Action</h3>
                        <div class="stat-value">
                            {max(audit_data.get('action_types', [{'type': 'N/A', 'count': 0}]), key=lambda x: x['count'])['type'] if audit_data.get('action_types') else 'N/A'}
                        </div>
                        <div class="stat-description">Most frequently performed</div>
                    </div>
                </div>
                
                {f'<div class="figure"><h3>Daily Activity</h3><img src="{figures.get("activity", "")}" alt="Daily Activity"><p class="figure-caption">Activity trend showing label operations over time.</p></div>' if "activity" in figures else ''}
                
                {f'<div class="figure"><h3>Actions by Type</h3><img src="{figures.get("actions", "")}" alt="Actions by Type"><p class="figure-caption">Distribution of different types of label operations.</p></div>' if "actions" in figures else ''}
                
                {f'<div class="figure"><h3>User Activity</h3><img src="{figures.get("users", "")}" alt="User Activity"><p class="figure-caption">Top users by label activity.</p></div>' if "users" in figures else ''}
                
                {f'<h3>User Activity Details</h3>{pd.DataFrame(audit_data.get("users", [])).head(10).to_html(index=False, classes="display")}' if audit_data.get('users') else '<p>No user activity data available</p>'}
                
                <p class="metadata">Note: Showing top 10 users only.</p>
                
                <div class="insights">
                    <h3>Activity Insights</h3>
                    <p>
                        {f"Over the past {lookback_days} days, there have been {audit_data.get('actions_count', 0)} label-related operations performed by {len(audit_data.get('users', []))} users." if audit_data.get('actions_count') else "No activity data is available for analysis."}
                        {f" The most common action was '{max(audit_data.get('action_types', [{'type': 'N/A', 'count': 0}]), key=lambda x: x['count'])['type']}', representing {max(audit_data.get('action_types', [{'type': 'N/A', 'count': 0}]), key=lambda x: x['count'])['count']} operations." if audit_data.get('action_types') else ""}
                    </p>
                    <p>
                        {f"User engagement is {len(audit_data.get('users', [])) / 10:.1f}/10 based on the number of active users." if audit_data.get('users') else ""}
                        {" Activity trends show " + ("increasing" if len(audit_data.get('daily_activity', [])) >= 2 and audit_data.get('daily_activity', [])[-1]['count'] > audit_data.get('daily_activity', [])[0]['count'] else "stable" if len(audit_data.get('daily_activity', [])) >= 2 and audit_data.get('daily_activity', [])[-1]['count'] == audit_data.get('daily_activity', [])[0]['count'] else "decreasing" if len(audit_data.get('daily_activity', [])) >= 2 else "unknown") + " usage over the analyzed period." if audit_data.get('daily_activity') else ""}
                    </p>
                </div>
            </div>
            
            <div class="section">
                <h2>Recommendations</h2>
                <div class="recommendations">
                    <h3>Optimize Label Structure</h3>
                    <p>
                        {f"Currently, {required_fields} out of {total_fields} fields ({required_fields/total_fields*100:.1f}%) are marked as required." if total_fields > 0 else "No field data is available."}
                        {" Consider reducing required fields to improve adoption if the ratio is above 30%." if total_fields > 0 and required_fields/total_fields > 0.3 else " Your balance of required vs. optional fields looks good." if total_fields > 0 else ""}
                    </p>
                    <p>
                        {f"There are {disabled_labels} disabled labels ({disabled_labels/total_labels*100:.1f}% of total)." if total_labels > 0 else ""}
                        {" Consider cleaning up by deleting unused disabled labels to maintain a streamlined taxonomy." if disabled_labels > 0 else ""}
                    </p>
                </div>
                
                <div class="recommendations">
                    <h3>Drive Adoption</h3>
                    <ul>
                        <li>Regularly review unused labels to maintain a clean environment.</li>
                        <li>Consider standardizing label naming conventions for better organization.</li>
                        <li>Provide training to users on proper label application.</li>
                        <li>Review required fields to ensure they add value without creating barriers to adoption.</li>
                        <li>Create documentation for your label taxonomy to help users understand when and how to use each label.</li>
                    </ul>
                </div>
                
                <div class="recommendations">
                    <h3>Technical Improvements</h3>
                    <ul>
                        <li>Implement batch processing for applying labels to multiple files.</li>
                        <li>Set up regular reporting to monitor label usage and trends.</li>
                        <li>Consider automating label application based on file content or location.</li>
                        <li>Integrate label information into your document lifecycle management processes.</li>
                    </ul>
                </div>
            </div>
            
            <footer>
                <p>Generated using Legal Drive Labels Manager v0.1.0</p>
                <p>Report period: {(datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}</p>
            </footer>
        </body>
        </html>
        """
        
        return html

    def create_text_report(self, lookback_days: int = 30) -> str:
        """
        Create a plain text summary report of label usage.
        
        Args:
            lookback_days: Number of days to include in activity analysis
            
        Returns:
            Formatted text report
        """
        # Get label usage statistics
        usage_stats = self.statistics.count_labels_by_usage()
        
        # Get audit data
        audit_data = self.statistics.analyze_audit_log(days=lookback_days)
        
        # Generate timestamp
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        # Calculate summary statistics
        total_labels = len(usage_stats)
        total_files = sum(item['file_count'] for item in usage_stats) if usage_stats else 0
        published_labels = sum(1 for item in usage_stats if item['state'] == 'PUBLISHED')
        disabled_labels = sum(1 for item in usage_stats if item['state'] == 'DISABLED')
        total_fields = sum(item['fields'] for item in usage_stats) if usage_stats else 0
        required_fields = sum(item['required_fields'] for item in usage_stats) if usage_stats else 0
        
        # Build report sections
        report = []
        
        # Header
        report.append("=" * 80)
        report.append("GOOGLE DRIVE LABELS USAGE REPORT")
        report.append("=" * 80)
        report.append(f"Generated on: {timestamp}")
        report.append(f"Period: Last {lookback_days} days")
        report.append("")
        
        # Summary section
        report.append("-" * 40)
        report.append("SUMMARY")
        report.append("-" * 40)
        report.append(f"Total labels: {total_labels}")
        report.append(f"Published labels: {published_labels}")
        report.append(f"Disabled labels: {disabled_labels}")
        report.append(f"Total files with labels: {total_files}")
        report.append(f"Total fields across all labels: {total_fields}")
        report.append(f"Required fields: {required_fields} ({required_fields/total_fields*100:.1f}% of total)" if total_fields > 0 else "Required fields: 0")
        report.append(f"Active users: {len(audit_data.get('users', []))}")
        report.append(f"Total actions recorded: {audit_data.get('actions_count', 0)}")
        report.append("")
        
        # Top labels section
        report.append("-" * 40)
        report.append("TOP 10 LABELS BY USAGE")
        report.append("-" * 40)
        report.append(f"{'LABEL':<40} {'STATE':<15} {'FILES':<10} {'FIELDS':<10}")
        report.append("-" * 75)
        
        # Sort by usage
        sorted_stats = sorted(usage_stats, key=lambda x: x['file_count'], reverse=True)
        
        for item in sorted_stats[:10]:
            report.append(f"{item['title']:<40} {item['state']:<15} {item['file_count']:<10} {item['fields']:<10}")
        
        report.append("")
        
        # Activity section
        if audit_data.get('action_types'):
            report.append("-" * 40)
            report.append("ACTIVITY BY TYPE")
            report.append("-" * 40)
            report.append(f"{'ACTION TYPE':<40} {'COUNT':<10}")
            report.append("-" * 50)
            
            # Sort by count
            sorted_actions = sorted(audit_data['action_types'], key=lambda x: x['count'], reverse=True)
            
            for item in sorted_actions:
                report.append(f"{item['type']:<40} {item['count']:<10}")
                
            report.append("")
        
        # Top users section
        if audit_data.get('users'):
            report.append("-" * 40)
            report.append("TOP USERS")
            report.append("-" * 40)
            report.append(f"{'USER':<50} {'ACTIONS':<10}")
            report.append("-" * 60)
            
            # Sort by count
            sorted_users = sorted(audit_data['users'], key=lambda x: x['count'], reverse=True)
            
            for item in sorted_users[:5]:
                report.append(f"{item['user']:<50} {item['count']:<10}")
                
            report.append("")
        
        # Daily activity summary
        if audit_data.get('daily_activity'):
            report.append("-" * 40)
            report.append("DAILY ACTIVITY SUMMARY")
            report.append("-" * 40)
            
            # Find peak day
            peak_day = max(audit_data['daily_activity'], key=lambda x: x['count']) if audit_data['daily_activity'] else {'date': 'N/A', 'count': 0}
            
            report.append(f"Peak day: {peak_day['date']} with {peak_day['count']} actions")
            
            # Calculate average daily actions
            avg_actions = sum(day['count'] for day in audit_data['daily_activity']) / len(audit_data['daily_activity']) if audit_data['daily_activity'] else 0
            
            report.append(f"Average daily actions: {avg_actions:.1f}")
            report.append("")
        
        # Recommendations
        report.append("-" * 40)
        report.append("RECOMMENDATIONS")
        report.append("-" * 40)
        report.append("1. Regularly review unused labels to maintain a clean environment.")
        report.append("2. Consider standardizing label naming conventions for better organization.")
        report.append("3. Provide training to users on proper label application.")
        report.append("4. Review required fields to ensure they add value without creating barriers.")
        report.append("5. Set up regular reporting to monitor label usage trends.")
        report.append("")
        
        # Footer
        report.append("=" * 80)
        report.append("Generated using Legal Drive Labels Manager v0.1.0")
        report.append(f"Report period: {(datetime.now() - timedelta(days=lookback_days)).strftime('%Y-%m-%d')} to {datetime.now().strftime('%Y-%m-%d')}")
        report.append("=" * 80)
        
        return "\n".join(report)