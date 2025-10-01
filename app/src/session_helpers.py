import os
import pprint
import shutil
import traceback
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QTreeWidgetItemIterator, QMessageBox
from datetime import datetime
from app.utils import tr, find_firefox_profiles

class SessionHelper:
    """Helper class for session management operations"""
    
    def __init__(self, logger, status_bar, session_loader, parent_widget=None):
        self.logger = logger
        self.status_bar = status_bar
        self.session_loader = session_loader
        self.parent_widget = parent_widget
    
    def get_window_id_from_tree_item(self, item, session_widget):
        """Get window ID by traversing up the tree structure to find the window"""
        current = item
        while current:
            parent = current.parent()
            if parent is None:
                # This is a top-level item, check if it's a window
                data = current.data(0, Qt.UserRole)
                if data and data.get('type') == 'window':
                    # Return the window index based on position in tree
                    root = session_widget.invisibleRootItem()
                    for i in range(root.childCount()):
                        if root.child(i) == current:
                            return i
                break
            elif parent == session_widget.invisibleRootItem():
                # Parent is root, so current item is a window
                data = current.data(0, Qt.UserRole)
                if data and data.get('type') == 'window':
                    # Find the index of this window in the root
                    for i in range(parent.childCount()):
                        if parent.child(i) == current:
                            return i
                break
            current = parent
        
        # Return None instead of 0 to indicate an error condition
        self.logger.warning("Could not determine window ID from tree item - this indicates a corrupted session structure")
        return None

    def get_group_id_for_window(self, new_group_id, target_window_id):
        """Get the appropriate group ID for the target window"""
        if new_group_id is None:
            return None
            
        try:
            json_data = self.session_loader.session_processor.json_data
            if not json_data or 'windows' not in json_data:
                return None
                
            if target_window_id >= len(json_data['windows']):
                return None
                
            target_window = json_data['windows'][target_window_id]
            
            # Check if the group exists in the target window
            if 'groups' in target_window:
                for group in target_window['groups']:
                    if group.get('id') == new_group_id:
                        return new_group_id
            
            # Group doesn't exist in target window - return None for ungrouped
            self.logger.info(f"Group {new_group_id} doesn't exist in window {target_window_id}, moving as ungrouped")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting group ID for window: {e}")
            return None

    def move_tab_between_windows(self, raw_tab, old_window_id, new_window_id, new_group_id):
        """Move a tab between windows in the raw JSON structure"""
        try:
            json_data = self.session_loader.session_processor.json_data
            if not json_data or 'windows' not in json_data:
                self.logger.warning("No JSON data or windows found")
                return False
            
            # Validate window IDs - None indicates corrupted structure
            if old_window_id is None or new_window_id is None:
                self.logger.error("Invalid window IDs detected - session file may be corrupted")
                self.status_bar.show_message(tr("Session file appears to be corrupted", "error"), message_type="error")
                return False
            
            # Firefox uses array index as window ID (0-based)
            if old_window_id >= len(json_data['windows']) or new_window_id >= len(json_data['windows']):
                self.logger.warning(f"Invalid window IDs: old={old_window_id}, new={new_window_id}, available={len(json_data['windows'])}")
                return False
            
            old_window = json_data['windows'][old_window_id]
            new_window = json_data['windows'][new_window_id]
            
            # Remove tab from old window
            tab_removed = False
            if 'tabs' in old_window:
                for i, tab in enumerate(old_window['tabs']):
                    if tab is raw_tab:
                        old_window['tabs'].pop(i)
                        tab_removed = True
                        self.logger.info(f"Removed tab from window {old_window_id} at position {i}")
                        break
            
            if not tab_removed:
                self.logger.warning("Could not find tab to remove from old window")
                return False
            
            # Handle group assignment
            if new_group_id is not None:
                # Validate that the target group actually exists in the target window
                group_exists = False
                if 'groups' in new_window:
                    for group in new_window['groups']:
                        if group.get('id') == new_group_id:
                            group_exists = True
                            break
                
                if group_exists:
                    raw_tab['groupId'] = new_group_id
                    self.logger.info(f"Set tab groupId to: {new_group_id} (group exists in target window)")
                else:
                    # CRITICAL ERROR: Group doesn't exist - abort the move!
                    # First, add the tab back to the old window to prevent data loss
                    old_window['tabs'].insert(i if i < len(old_window['tabs']) else len(old_window['tabs']), raw_tab)
                    
                    self.logger.error(f"CRITICAL: Group {new_group_id} doesn't exist in target window {new_window_id} - ABORTING MOVE")
                    self.status_bar.show_message(tr("Error: Target group does not exist in destination window", "error"), message_type="error")
                    return False
            else:
                # Moving to ungrouped - remove groupId
                if 'groupId' in raw_tab:
                    del raw_tab['groupId']
                    self.logger.info("Removed groupId (moving to ungrouped)")
            
            # Add tab to new window
            if 'tabs' not in new_window:
                new_window['tabs'] = []
            
            new_window['tabs'].append(raw_tab)
            self.logger.info(f"Added tab to window {new_window_id}")
            
            # Update window selected tab index if necessary
            if 'selected' in old_window and old_window['selected'] > len(old_window.get('tabs', [])):
                old_window['selected'] = max(1, len(old_window.get('tabs', [])))
            
            self.logger.info(f"Successfully moved tab between windows: {old_window_id} -> {new_window_id}")
            return True
            
        except Exception as e:
            self.logger.error(f"Error moving tab between windows: {e} |#| ({type(e).__name__})", exc_info=True)
            # Try to restore the tab to prevent data loss
            try:
                if 'old_window' in locals() and 'raw_tab' in locals():
                    if 'tabs' not in old_window:
                        old_window['tabs'] = []
                    old_window['tabs'].append(raw_tab)
                    self.logger.info("Restored tab to original window after error")
            except:
                pass
            raise

    def move_tab_to_new_group(self, item, new_group_name, enriched_tab, raw_tab, 
                             session_widget, group_to_window_map, group_list):
        """Move a tab to a new group, handling cross-window moves"""
        old_parent = item.parent()
        if old_parent and old_parent.text(0).startswith(new_group_name):
            return None

        # Get current window ID from the tree structure
        old_window_id = self.get_window_id_from_tree_item(item, session_widget)
        
        # IMPORTANT: Also get window info from enriched_tab data
        old_window_from_tab = enriched_tab.get('window_index', 0) if enriched_tab else 0
        
        # Use the more reliable source
        if old_window_id is None:
            old_window_id = old_window_from_tab
            self.logger.info(f"Using window_index from tab data: {old_window_id}")
        
        # Find the target group and its window by examining all tabs
        target_group_info = None
        new_window_id = None
        ungrouped_text = tr("Ungrouped", "main")
        
        if new_group_name == ungrouped_text:
            # Moving to ungrouped - stay in current window
            new_window_id = old_window_id
            self.logger.info(f"Moving to ungrouped in current window {old_window_id}")
        else:
            # Find the target group by searching through session data
            # We need to determine which window this group belongs to
            json_data = self.session_loader.session_processor.json_data
            if json_data and 'windows' in json_data:
                for window_idx, window in enumerate(json_data['windows']):
                    if 'groups' in window:
                        for group in window['groups']:
                            if group.get('name') == new_group_name:
                                # Found the group - create target_group_info with window information
                                target_group_info = group.copy()
                                target_group_info['window_index'] = window_idx
                                new_window_id = window_idx
                                self.logger.info(f"Found target group '{new_group_name}' with ID {group.get('id')} in window {window_idx}")
                                break
                    if target_group_info:
                        break
            
            # If still not found, error
            if not target_group_info:
                self.logger.error(f"CRITICAL: Group '{new_group_name}' not found in any window - ABORTING MOVE")
                self.status_bar.show_message(tr("Error: Group '{0}' not found in any window", "error").format(new_group_name), message_type="error")
                return None
        
        # Validate window IDs
        if old_window_id is None:
            self.logger.error("Could not determine source window ID - aborting move")
            self.status_bar.show_message(tr("Error: Could not determine source window", "error"), message_type="error")
            return None
            
        if new_window_id is None:
            self.logger.error(f"Could not determine target window for group '{new_group_name}' - aborting move")
            self.status_bar.show_message(tr("Error: Could not determine target window", "error"), message_type="error")
            return None
        
        # Check if we need to move between windows
        needs_window_move = old_window_id != new_window_id
        self.logger.info(f"Move analysis: old_window={old_window_id}, new_window={new_window_id}, needs_window_move={needs_window_move}")
        
        if needs_window_move and raw_tab and enriched_tab:
            try:
                # Cross-window move
                new_group_id = target_group_info['id'] if target_group_info else None
                
                # Attempt to move tab in JSON structure
                success = self.move_tab_between_windows(raw_tab, old_window_id, new_window_id, new_group_id)
                
                if not success:
                    self.logger.error("Failed to move tab between windows")
                    return None
                
                # Update enriched tab data only if move was successful - USE CORRECT FIELD NAME!
                enriched_tab['window_index'] = new_window_id  # NOT window_id!
                enriched_tab['group_id'] = new_group_id
                
                # Find target parent in tree view for cross-window move
                new_parent = self._find_target_parent_cross_window(session_widget, new_group_name, new_window_id)
                
                if new_parent and old_parent:
                    # Remove from old parent
                    taken_item = old_parent.takeChild(old_parent.indexOfChild(item))
                    # Add to new parent
                    new_parent.addChild(taken_item)
                    session_widget.setCurrentItem(taken_item)
                    
                    old_count = old_parent.childCount()
                    new_count = new_parent.childCount()
                    
                    self.logger.info(f"Visual cross-window move completed: {old_count} -> {new_count}")
                    
                    return {'window_move_completed': True, 'visual_move_completed': True, 
                           'old_parent': old_parent, 'new_parent': new_parent,
                           'old_count': old_count, 'new_count': new_count}
                else:
                    self.logger.warning("Could not find target parent for visual cross-window move")
                    return {'window_move_completed': True}
                
            except Exception as e:
                self.logger.error(f"Error moving tab between windows: {e}")
                self.status_bar.show_message(tr("Error moving tab between windows", "error"), message_type="error")
                return None
        
        # Same window move
        else:
            if new_group_name != ungrouped_text and target_group_info:
                # Moving to a group in same window
                if raw_tab:
                    raw_tab['groupId'] = target_group_info['id']
                enriched_tab['group_id'] = target_group_info['id']
                self.logger.info(f"Updated tab to group '{new_group_name}' (ID: {target_group_info['id']}) in same window {old_window_id}")
            else:
                # Moving to ungrouped in same window
                if raw_tab and 'groupId' in raw_tab:
                    del raw_tab['groupId']
                enriched_tab['group_id'] = None
                self.logger.info(f"Moved tab to ungrouped in same window {old_window_id}")

            # Continue with visual UI move within same window
            new_parent = None
            iterator = QTreeWidgetItemIterator(session_widget)

            while iterator.value():
                potential_parent = iterator.value()
                parent_data = potential_parent.data(0, Qt.UserRole)
                if parent_data and parent_data.get("type") == "group" and parent_data.get("group_name") == new_group_name:
                    new_parent = potential_parent
                    break
                elif new_group_name == tr("Ungrouped", "main") and potential_parent.text(0).startswith(tr("Ungrouped", "Groups")):
                    new_parent = potential_parent
                    break
                iterator += 1

            if new_parent and old_parent:
                taken_item = old_parent.takeChild(old_parent.indexOfChild(item))
                new_parent.addChild(taken_item)
                session_widget.setCurrentItem(taken_item)

                old_count = old_parent.childCount()
                new_count = new_parent.childCount()

                return {'visual_move_completed': True, 'old_parent': old_parent, 'new_parent': new_parent,
                        'old_count': old_count, 'new_count': new_count}
        
        return None

    def _find_target_parent_cross_window(self, session_widget, target_group_name, target_window_id):
        """Find the target parent in tree view for cross-window moves"""
        """-> This was added from Claude AI - i dont have a clue how to fix the problem by my own"""
        ungrouped_text = tr("", "main")
        
        # First, find the target window by traversing the tree structure
        root = session_widget.invisibleRootItem()
        target_window_item = None
        
        # Find the window item by index (windows are top-level items)
        if target_window_id < root.childCount():
            potential_window = root.child(target_window_id)
            window_data = potential_window.data(0, Qt.UserRole)
            if window_data and window_data.get("type") == "window":
                target_window_item = potential_window
                self.logger.debug(f"Found target window item for window {target_window_id}")
        
        if not target_window_item:
            self.logger.warning(f"Could not find window item for window {target_window_id}")
            return None
        
        # Now search within this window for the target group
        for i in range(target_window_item.childCount()):
            potential_parent = target_window_item.child(i)
            parent_data = potential_parent.data(0, Qt.UserRole)
            
            if not parent_data:
                continue
                
            if parent_data.get("type") == "group":
                # Check if this is the target group
                if parent_data.get("group_name") == target_group_name:
                    self.logger.info(f"Found target group '{target_group_name}' in window {target_window_id}")
                    return potential_parent
            elif (target_group_name == ungrouped_text and 
                  potential_parent.text(0).startswith(tr("Ungrouped", "Groups"))):
                # Found ungrouped tabs in the target window
                self.logger.info(f"Found ungrouped in window {target_window_id}")
                return potential_parent
        
        # If we didn't find the group, maybe it's nested deeper - do a recursive search within the window
        def search_recursive(parent_item, depth=0):
            if depth > 3:  # Prevent infinite recursion
                return None
                
            for i in range(parent_item.childCount()):
                child = parent_item.child(i)
                child_data = child.data(0, Qt.UserRole)
                
                if child_data:
                    if child_data.get("type") == "group" and child_data.get("group_name") == target_group_name:
                        return child
                    elif (target_group_name == ungrouped_text and 
                          child.text(0).startswith(tr("Ungrouped", "Groups"))):
                        return child
                
                # Recursive search
                result = search_recursive(child, depth + 1)
                if result:
                    return result
            return None
        
        recursive_result = search_recursive(target_window_item)
        if recursive_result:
            self.logger.info(f"Found target '{target_group_name}' in window {target_window_id} via recursive search")
            return recursive_result
        
        self.logger.warning(f"Could not find target parent for group '{target_group_name}' in window {target_window_id}")
        return None

    # All the things that has something to do with handling sessions
    def save_session_changes(self, current_file_path, session_tabs, parent_widget):
        """Save session changes to file with user confirmation"""
        if not self.session_loader.session_processor.json_data or not current_file_path:
            self.status_bar.show_message(tr('No session file loaded to export', 'error'), message_type='error')
            self.logger.error(f"{tr('No session file loaded to export', 'error')}! (Since the button is disabled without valid session data its very unlikley that you see this message. But let me tell You: From the Bottom of my Heart: I love you, you are doing great! Your are an amazing creation of God!)")
            return False

                
        reply = QMessageBox.question(
            parent_widget, 
            tr('Confirm Overwrite', 'MessageBox_quest'),
            f"{tr('You are about to overwrite the session file', 'MessageBox_quest')}. \n\n{tr('However, there is still a backup in the "untouched" folder.', 'MessageBox_quest')}",
            QMessageBox.Yes | QMessageBox.No, QMessageBox.No
        )

        if reply == QMessageBox.Yes:
            try:
                self.session_loader.session_processor.write_jsonlz4()
                self.status_bar.show_message(tr("Saved", "main"), message_type="success")
                return True
            except Exception as e:
                self.logger.error(f"{tr('Error overwriting session file', 'error')}: {current_file_path}: {e} |#| ({type(e).__name__})", exc_info=True)
                self.status_bar.show_message(tr("Error overwriting session file", "error"), message_type="error")
                return False
        else:
            self.status_bar.show_message(tr("You Cancelled", "info"), message_type="warning")
            return False


    def replace_session(self, current_file_path, session_tabs):
        try:
            confirm = self.save_session_changes(current_file_path, session_tabs, self.parent_widget)
            
            if confirm is False:
                return

            restore_path = current_file_path
            restore_dir = os.path.dirname(restore_path)

            profile_info_path = os.path.join(restore_dir, 'profile.txt')
            if not os.path.exists(profile_info_path):
                QMessageBox.warning(
                    self.parent_widget, 
                    tr("Error", "MessageBox"), 
                    tr("No Profile information found.\nThe Session is only saved in the backup folder.", "MessageBox_warn")
                )
                return
                
            with open(profile_info_path, 'r', encoding='utf-8') as f:
                profile_info = f.read().strip()
            
            if '|' not in profile_info:
                QMessageBox.warning(
                    self, 
                    tr("Error", "MessageBox"),
                    tr("Unkown Profile information.", "MessageBox_warn") 
                )
                return
                
            profile_id, import_date = profile_info.split('|', 1)

            all_profiles = find_firefox_profiles()
            target_profile_dir = None
            
            for profile_dir in all_profiles:
                if profile_id in os.path.basename(profile_dir):
                    target_profile_dir = profile_dir
                    break
            
            if not target_profile_dir:
                QMessageBox.warning(
                    self.parent_widget,
                    tr("Error", "Error"),
                    tr("Profile '{0}' not found.\n\nWhat a shame!", "Error", profile_id)
                )
                return
            
            # Show restore type selection dialog
            restore_type = self._show_restore_type_dialog()
            if restore_type is None:
                self.status_bar.show_message(tr("You Cancelled", "main"), message_type="warning")
                return # User cancelled
            
            success = self._replace_session_files(target_profile_dir, restore_dir, restore_path, restore_type, import_date)
            
            if success:
                self.status_bar.show_message(tr("Session Replaced", "main"), message_type="success")
            else:
                self.status_bar.show_message(tr("You cancelled", "info"), message_type="warning")
                                
        except Exception as e:
            QMessageBox.critical(
                self.parent_widget,
                tr("Error", "Error"),
                f"{tr('Could not replace Session', 'Error')}: \n {str(e)}"
            )
            self.logger.error(f"{tr('Could not replace Session', 'Error')}: {e} |#| ({type(e).__name__})", exc_info=True)


    def _show_restore_type_dialog(self):
        #TODO: Move to seperate dialog file?
        """Show dialog to choose restore type (sessionstore, recovery, or previous)"""
        from PySide6.QtWidgets import QDialog, QVBoxLayout, QRadioButton, QButtonGroup, QPushButton, QHBoxLayout, QLabel
        
        dialog = QDialog(self.parent_widget)
        dialog.setWindowTitle(tr("Choose Restore Type", "ReplaceSession"))
        dialog.setModal(True)
        dialog.resize(400, 200)
        
        layout = QVBoxLayout(dialog)
        
        # Info label
        info_label = QLabel(tr("Choose how to restore the session:", "ReplaceSession"))
        layout.addWidget(info_label)
        
        # Radio buttons
        self.restore_button_group = QButtonGroup(dialog)
        
        self.sessionstore_radio = QRadioButton(f"{tr('Current Session', 'ReplaceSession')} (sessionstore.jsonlz4) - {tr('Recommended', 'ReplaceSession')}")
        self.sessionstore_radio.setChecked(True)  # Default selection
        self.restore_button_group.addButton(self.sessionstore_radio, 0)
        layout.addWidget(self.sessionstore_radio)
        self.recovery_radio = QRadioButton(f"{tr('Recovery Session', 'ReplaceSession')} (recovery.jsonlz4)")
        self.restore_button_group.addButton(self.recovery_radio, 1)
        layout.addWidget(self.recovery_radio)

        self.previous_radio = QRadioButton(f"{tr('Previous Session', 'ReplaceSession')} (previous.jsonlz4)")
        self.restore_button_group.addButton(self.previous_radio, 2)
        layout.addWidget(self.previous_radio)
        
        # Buttons
        button_layout = QHBoxLayout()
        ok_button = QPushButton(tr("Yes", "main"))
        cancel_button = QPushButton(tr("Cancel", "main"))
        
        ok_button.clicked.connect(dialog.accept)
        cancel_button.clicked.connect(dialog.reject)
        
        button_layout.addStretch()
        button_layout.addWidget(cancel_button)
        button_layout.addWidget(ok_button)
        layout.addLayout(button_layout)
        
        if dialog.exec() == QDialog.Accepted:
            return self.restore_button_group.checkedId()
        return None

    def _replace_session_files(self, profile_dir, restore_dir, restore_path, restore_type, import_date):
        try:
            # Define target paths based on restore type
            file_mappings = {
                0: ("sessionstore.jsonlz4", "sessionstore.jsonlz4"),
                1: ("recovery.jsonlz4", os.path.join("sessionstore-backups", "recovery.jsonlz4")), 
                2: ("previous.jsonlz4", os.path.join("sessionstore-backups", "previous.jsonlz4")) 
            }
            
            if restore_type not in file_mappings:
                QMessageBox.warning(
                    self.parent_widget, 
                    tr("Error", "MessageBox"),
                    tr('Invalid restore type selected.', 'session_helper')
                )
                self.logger.error(f"{tr('Invalid restore type selected', 'session_helper')}.: {restore_type} - how did you manage to do that?")
                return False
            
            source_filename, target_relative_path = file_mappings[restore_type]
            target_path = os.path.join(profile_dir, target_relative_path)
            target_dir = os.path.dirname(target_path)

            # Create target directory if needed (in case the sessionstore-backups folder is missing)
            os.makedirs(target_dir, exist_ok=True)
            
            source_session = self.parent_widget.current_file_path
            
            if not os.path.exists(source_session):
                QMessageBox.warning(
                    self.parent_widget,
                    tr("Error", "MessageBox"),
                    f"{tr('Something went (terrible) Wrong', 'MessageBox')} \n {tr('I couldn\'t find the source file', 'MessageBox')}..."
                )
                return False
                
            if not os.access(profile_dir, os.W_OK):
                QMessageBox.warning(
                    self.parent_widget, 
                    tr("Error", "MessageBox"),
                    f"{tr('I\'m not allowed to write to the Firefox-Profile-Folder', 'MessageBox_warn')}.\n{tr('Be sure that Firefox isn\'t running.', 'MessageBox_warn')}"
                )
                return False
            
            # Check file age and show warning if needed
            file_type_names = {
                0: "sessionstore.jsonlz4",
                1: "recovery.jsonlz4", 
                2: "previous.jsonlz4"
            }
            
            if not self._check_file_age_warning(target_path, import_date, file_type_names[restore_type]):
                return False  # User cancelled due to file age warning
            
            # If sessionstore is selected, check Firefox startup preference
            if restore_type == 0:  # sessionstore
                if not self._check_firefox_startup_preference(profile_dir):
                    return False  # User cancelled or error occurred
            
            # Create backup
            backup_time = datetime.now().strftime("%Y%m%d_%H%M%S")
            backup_profile_dir = os.path.join(restore_dir, "original_backup")
            os.makedirs(backup_profile_dir, exist_ok=True)

            # Backup existing target file if it exists - there are never enough backups. Maybe remove, because we have the untouched folder?
            if os.path.exists(target_path):
                backup_filename = f"{source_filename.replace('.jsonlz4', '')}_{backup_time}.jsonlz4"
                shutil.copy2(target_path, os.path.join(backup_profile_dir, backup_filename))
            
            # Copy source to target
            shutil.copy2(source_session, target_path)

            # Log the replacement
            with open(os.path.join(restore_dir, "replace_log.txt"), 'a', encoding='utf-8') as f:
                restore_type_names = {
                    0: "sessionstore",
                    1: "recovery", 
                    2: "previous"
                }
                f.write(f"{datetime.now().strftime('%d.%m.%Y %H:%M')} - "
                    f"Session replaced as {restore_type_names[restore_type]} in: {profile_dir}\n")
            
            return True
            
        except PermissionError as e:
            QMessageBox.warning(
                self.parent_widget, 
                tr("Error", "MessageBox"),
                f"{tr('No write permissions for the Firefox profile.', 'MessageBox_warn')}\n{tr('Please close Firefox completely and try again.', 'MessageBox_warn')}"
            )
            self.logger.error(f"Permission error replacing session files: {e} |#| ({type(e).__name__})", exc_info=True)
            return False
        
        except Exception as e:
            QMessageBox.critical(
                self.parent_widget,
                tr("Error", "MessageBox"),
                f"{tr('Error replacing session files', 'Error')}: {str(e)}"
            )
            self.logger.error(f"{tr('Error replacing session files', 'Error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            return False
        
    
    def _check_file_age_warning(self, target_file_path, import_date_str, file_type):
        """Check if target file is newer than imported session and show warning"""
        if not os.path.exists(target_file_path):
            return True  # File doesn't exist, no warning needed
        
        # Parse import date
        import_date = self._parse_import_date(import_date_str)
        if not import_date:
            return True  # Can't parse date, proceed without warning
        
        # Get target file modification time
        target_file_mtime = datetime.fromtimestamp(os.path.getmtime(target_file_path))
        
        # Compare dates
        if target_file_mtime > import_date:
            # Target file is newer, show warning
            target_file_time_str = target_file_mtime.strftime("%d.%m.%Y %H:%M")
            import_time_str = import_date.strftime("%d.%m.%Y %H:%M")
            
            reply = QMessageBox.question(
                self.parent_widget,
                tr("File Age Warning", "ReplaceSession"),
                f"{tr("The existing file is newer than the imported session", 'ReplaceSession')}.\n"
                f"{tr("Existing file","ReplaceSession")}: {target_file_time_str}\n"
                f"{tr("Imported session","ReplaceSession")}: {import_time_str}\n\n"
                f"{tr("Do you want to continue anyway?", 'ReplaceSession')}",

                QMessageBox.Yes | QMessageBox.No,
                QMessageBox.No
            )
            return reply == QMessageBox.Yes
        
        return True  # Target file is older or same age, proceed
    

    def _parse_import_date(self, date_string):
        """Parse import date from profile.txt format: '16.09.2025 18:40'"""
        try:
            return datetime.strptime(date_string, "%d.%m.%Y %H:%M")
        except ValueError as e:
            self.logger.error(f"{tr('Error replacing session files', 'error')}. {tr('Could not parse import date', 'error')}: {e} |#| ({type(e).__name__})", exc_info=True)
            self.status_bar.show_message(f"{tr('Error replacing session files', 'error')}", message_type="error")
            return None
        

    def _check_firefox_startup_preference(self, profile_dir):
        """Check and optionally configure Firefox startup preference for sessionstore replacement"""
        
        prefs_path = os.path.join(profile_dir, "prefs.js")
        user_prefs_path = os.path.join(profile_dir, "user.js")
        exist_prefs = os.path.exists(prefs_path)
        exist_user_prefs = os.path.exists(user_prefs_path)

        if not os.path.exists(user_prefs_path) and not os.path.exists(prefs_path):
            # no file exists, nothing to do
            self.logger.error(f"{tr('No files found', 'error')} (user.js / prefs.js)")
            return False

        try:
            import re

            if exist_user_prefs:
                # Read user.js file if it exists
                with open(user_prefs_path, 'r', encoding='utf-8') as f:
                    content = f.read()
            elif exist_prefs:
                # Read prefs.js file
                with open(prefs_path, 'r', encoding='utf-8') as f:
                    content = f.read()


            # Look for browser.startup.page preference
            startup_page_pattern = r'user_pref\("browser\.startup\.page",\s*(\d+)\);'
            match = re.search(startup_page_pattern, content)

            if match:
                startup_page_value = int(match.group(1))
                if startup_page_value == 3:
                    return True  # Already configured correctly
                else:
                    # Wrong value, ask user to fix it
                    return self._show_firefox_startup_dialog()
            else:
                # Preference not found, ask user to add it
                return self._show_firefox_startup_dialog()

        except Exception as e:
            self.logger.error(f"Error checking Firefox startup preference: {e} |#| ({type(e).__name__})", exc_info=True)
            return True  # Continue anyway if we can't read the file

    def _show_firefox_startup_dialog(self):
        from app.ui.dialogs import FirefoxConfigDialog
        """Show dialog asking user to configure Firefox startup preference"""
        dialog = FirefoxConfigDialog(self.parent_widget)
        dialog.exec()
        
        user_choice = dialog.get_user_choice()
        
        if user_choice == "configured":
            # User says they configured it
            return True
        else:
            # User cancelled
            return False
        