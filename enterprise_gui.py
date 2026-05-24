"""
Enterprise LLM Suite - macOS GUI
Native Cocoa-based GUI for the Enterprise LLM Suite
"""
import sys
from pathlib import Path
import json
from datetime import datetime

try:
    import Cocoa
    from AppKit import (
        NSApplication, NSWindow, NSView, NSTextField, NSTextView,
        NSButton, NSScrollView, NSTableView, NSTableColumn,
        NSMenu, NSMenuItem, NSAlert, NSImage, NSColor,
        NSBox, NSSegmentedControl, NSTabView, NSTabViewItem,
        NSProgressIndicator, NSStatusBar, NSStatusItem,
        NSBezierPath, NSFont, NSRect, NSPoint, NSSize,
        NSApplicationActivationPolicyRegular
    )
    from Foundation import NSObject, NSTimer, NSMutableString, NSString
    from PyObjCTools import AppHelper
except ImportError:
    print("PyObjC required. Install with: pip install pyobjc-framework-Cocoa")
    sys.exit(1)

from enterprise_suite import (
    EnterpriseLLMSuite,
    create_enterprise_suite,
    ModelProvider,
    UserRole
)


class EnterpriseAppDelegate(NSObject):
    """Main application delegate."""
    
    def applicationDidFinishLaunching_(self, notification):
        """Called when app finishes launching."""
        self.suite = create_enterprise_suite()
        self.create_main_window()
        self.setup_menu()
        
    def create_main_window(self):
        """Create main application window."""
        rect = NSRect(NSPoint(0, 0), NSSize(1200, 800))
        self.window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
            rect,
            15,  # NSTitledWindowMask | NSClosableWindowMask | NSMiniaturizableWindowMask | NSResizableWindowMask
            2,   # NSBackingStoreBuffered
            False
        )
        self.window.setTitle_("Enterprise LLM Suite")
        self.window.center()
        self.window.setDelegate_(self)
        
        # Create tab view
        tab_rect = NSRect(NSPoint(20, 20), NSSize(1160, 760))
        self.tab_view = NSTabView.alloc().initWithFrame_(tab_rect)
        
        # Create tabs
        self.create_chat_tab()
        self.create_models_tab()
        self.create_documents_tab()
        self.create_analytics_tab()
        self.create_settings_tab()
        
        self.window.contentView().addSubview_(self.tab_view)
        self.window.makeKeyAndOrderFront_(None)
        
    def create_chat_tab(self):
        """Create chat interface tab."""
        tab_item = NSTabViewItem.alloc().initWithIdentifier_("chat")
        tab_item.setLabel_("Chat")
        
        # Chat view
        chat_view = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(1160, 760)))
        
        # Conversation list (left sidebar)
        list_rect = NSRect(NSPoint(0, 0), NSSize(250, 760))
        self.conv_list = NSTableView.alloc().initWithFrame_(list_rect)
        conv_column = NSTableColumn.alloc().initWithIdentifier_("title")
        conv_column.headerCell().setStringValue_("Conversations")
        self.conv_list.addTableColumn_(conv_column)
        self.conv_list.setDataSource_(self)
        self.conv_list.setDelegate_(self)
        
        list_scroll = NSScrollView.alloc().initWithFrame_(list_rect)
        list_scroll.setDocumentView_(self.conv_list)
        list_scroll.setHasVerticalScroller_(True)
        chat_view.addSubview_(list_scroll)
        
        # Chat area (right side)
        chat_rect = NSRect(NSPoint(260, 100), NSSize(900, 660))
        self.chat_view = NSTextView.alloc().initWithFrame_(chat_rect)
        self.chat_view.setEditable_(False)
        self.chat_view.setFont_(NSFont.systemFontOfSize_(12))
        
        chat_scroll = NSScrollView.alloc().initWithFrame_(chat_rect)
        chat_scroll.setDocumentView_(self.chat_view)
        chat_scroll.setHasVerticalScroller_(True)
        chat_view.addSubview_(chat_scroll)
        
        # Input field
        input_rect = NSRect(NSPoint(260, 20), NSSize(900, 70))
        self.input_field = NSTextView.alloc().initWithFrame_(input_rect)
        self.input_field.setFont_(NSFont.systemFontOfSize_(12))
        self.input_field.setString_("Type your message here...")
        chat_view.addSubview_(self.input_field)
        
        # Send button
        send_rect = NSRect(NSPoint(1070, 20), NSSize(90, 70))
        send_button = NSButton.alloc().initWithFrame_(send_rect)
        send_button.setTitle_("Send")
        send_button.setTarget_(self)
        send_button.setAction_("send_message:")
        chat_view.addSubview_(send_button)
        
        tab_item.setView_(chat_view)
        self.tab_view.addTabViewItem_(tab_item)
        
    def create_models_tab(self):
        """Create models management tab."""
        tab_item = NSTabViewItem.alloc().initWithIdentifier_("models")
        tab_item.setLabel_("Models")
        
        models_view = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(1160, 760)))
        
        # Models table
        table_rect = NSRect(NSPoint(20, 100), NSSize(1120, 640))
        self.models_table = NSTableView.alloc().initWithFrame_(table_rect)
        
        columns = ["Name", "Provider", "Size (MB)", "Quantization", "Status"]
        for col_id, title in enumerate(columns):
            column = NSTableColumn.alloc().initWithIdentifier_(str(col_id))
            column.headerCell().setStringValue_(title)
            self.models_table.addTableColumn_(column)
        
        self.models_table.setDataSource_(self)
        self.models_table.setDelegate_(self)
        
        table_scroll = NSScrollView.alloc().initWithFrame_(table_rect)
        table_scroll.setDocumentView_(self.models_table)
        table_scroll.setHasVerticalScroller_(True)
        models_view.addSubview_(table_scroll)
        
        # Load model button
        load_rect = NSRect(NSPoint(20, 20), NSSize(150, 60))
        load_button = NSButton.alloc().initWithFrame_(load_rect)
        load_button.setTitle_("Load Model")
        load_button.setTarget_(self)
        load_button.setAction_("load_model:")
        models_view.addSubview_(load_button)
        
        # Register model button
        register_rect = NSRect(NSPoint(180, 20), NSSize(150, 60))
        register_button = NSButton.alloc().initWithFrame_(register_rect)
        register_button.setTitle_("Register Model")
        register_button.setTarget_(self)
        register_button.setAction_("register_model:")
        models_view.addSubview_(register_button)
        
        tab_item.setView_(models_view)
        self.tab_view.addTabViewItem_(tab_item)
        
    def create_documents_tab(self):
        """Create documents/RAG tab."""
        tab_item = NSTabViewItem.alloc().initWithIdentifier_("documents")
        tab_item.setLabel_("Documents")
        
        docs_view = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(1160, 760)))
        
        # Documents table
        table_rect = NSRect(NSPoint(20, 100), NSSize(1120, 640))
        self.docs_table = NSTableView.alloc().initWithFrame_(table_rect)
        
        columns = ["Name", "Size", "Chunks", "Uploaded"]
        for col_id, title in enumerate(columns):
            column = NSTableColumn.alloc().initWithIdentifier_(str(col_id))
            column.headerCell().setStringValue_(title)
            self.docs_table.addTableColumn_(column)
        
        self.docs_table.setDataSource_(self)
        self.docs_table.setDelegate_(self)
        
        table_scroll = NSScrollView.alloc().initWithFrame_(table_rect)
        table_scroll.setDocumentView_(self.docs_table)
        table_scroll.setHasVerticalScroller_(True)
        docs_view.addSubview_(table_scroll)
        
        # Upload button
        upload_rect = NSRect(NSPoint(20, 20), NSSize(150, 60))
        upload_button = NSButton.alloc().initWithFrame_(upload_rect)
        upload_button.setTitle_("Upload Document")
        upload_button.setTarget_(self)
        upload_button.setAction_("upload_document:")
        docs_view.addSubview_(upload_button)
        
        # Search field
        search_rect = NSRect(NSPoint(180, 35), NSSize(400, 30))
        self.search_field = NSTextField.alloc().initWithFrame_(search_rect)
        self.search_field.setPlaceholderString_("Search documents...")
        docs_view.addSubview_(self.search_field)
        
        tab_item.setView_(docs_view)
        self.tab_view.addTabViewItem_(tab_item)
        
    def create_analytics_tab(self):
        """Create analytics tab."""
        tab_item = NSTabViewItem.alloc().initWithIdentifier_("analytics")
        tab_item.setLabel_("Analytics")
        
        analytics_view = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(1160, 760)))
        
        # Analytics display
        stats_rect = NSRect(NSPoint(20, 20), NSSize(1120, 720))
        self.analytics_view = NSTextView.alloc().initWithFrame_(stats_rect)
        self.analytics_view.setEditable_(False)
        self.analytics_view.setFont_(NSFont.systemFontOfSize_(12))
        
        stats_scroll = NSScrollView.alloc().initWithFrame_(stats_rect)
        stats_scroll.setDocumentView_(self.analytics_view)
        stats_scroll.setHasVerticalScroller_(True)
        analytics_view.addSubview_(stats_scroll)
        
        # Refresh button
        refresh_rect = NSRect(NSPoint(20, 20), NSSize(150, 60))
        refresh_button = NSButton.alloc().initWithFrame_(refresh_rect)
        refresh_button.setTitle_("Refresh")
        refresh_button.setTarget_(self)
        refresh_button.setAction_("refresh_analytics:")
        analytics_view.addSubview_(refresh_button)
        
        tab_item.setView_(analytics_view)
        self.tab_view.addTabViewItem_(tab_item)
        
    def create_settings_tab(self):
        """Create settings tab."""
        tab_item = NSTabViewItem.alloc().initWithIdentifier_("settings")
        tab_item.setLabel_("Settings")
        
        settings_view = NSView.alloc().initWithFrame_(NSRect(NSPoint(0, 0), NSSize(1160, 760)))
        
        # Settings display
        settings_rect = NSRect(NSPoint(20, 20), NSSize(1120, 720))
        self.settings_view = NSTextView.alloc().initWithFrame_(settings_rect)
        self.settings_view.setEditable_(False)
        self.settings_view.setFont_(NSFont.systemFontOfSize_(12))
        
        settings_scroll = NSScrollView.alloc().initWithFrame_(settings_rect)
        settings_scroll.setDocumentView_(self.settings_view)
        settings_scroll.setHasVerticalScroller_(True)
        settings_view.addSubview_(settings_scroll)
        
        # Export button
        export_rect = NSRect(NSPoint(20, 20), NSSize(150, 60))
        export_button = NSButton.alloc().initWithFrame_(export_rect)
        export_button.setTitle_("Export Suite")
        export_button.setTarget_(self)
        export_button.setAction_("export_suite:")
        settings_view.addSubview_(export_button)
        
        tab_item.setView_(settings_view)
        self.tab_view.addTabViewItem_(tab_item)
        
    def setup_menu(self):
        """Setup application menu."""
        main_menu = NSMenu.alloc().init()
        
        # App menu
        app_menu = NSMenu.alloc().init()
        app_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Enterprise LLM Suite", None, "")
        app_menu_item.setSubmenu_(app_menu)
        main_menu.addItem_(app_menu_item)
        
        # Quit item
        quit_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("Quit", "terminate:", "q")
        app_menu.addItem_(quit_item)
        
        # File menu
        file_menu = NSMenu.alloc().init()
        file_menu_item = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("File", None, "")
        file_menu_item.setSubmenu_(file_menu)
        main_menu.addItem_(file_menu_item)
        
        # New conversation
        new_conv = NSMenuItem.alloc().initWithTitle_action_keyEquivalent_("New Conversation", "new_conversation:", "n")
        new_conv.setTarget_(self)
        file_menu.addItem_(new_conv)
        
        NSApp().setMainMenu_(main_menu)
        
    # NSTableViewDataSource methods
    def numberOfRowsInTableView_(self, table_view):
        """Return number of rows for table."""
        if table_view == self.conv_list:
            return len(self.suite.conversations)
        elif table_view == self.models_table:
            return len(self.suite.models)
        elif table_view == self.docs_table:
            return len(self.suite.documents)
        return 0
    
    def tableView_objectValueForTableColumn_row_(self, table_view, column, row):
        """Return value for table cell."""
        col_id = column.identifier()
        
        if table_view == self.conv_list:
            convs = list(self.suite.conversations.values())
            if row < len(convs):
                return convs[row].title
                
        elif table_view == self.models_table:
            models = list(self.suite.models.values())
            if row < len(models):
                model = models[row]
                if col_id == "0":
                    return model.name
                elif col_id == "1":
                    return model.provider.value
                elif col_id == "2":
                    return str(model.size_mb)
                elif col_id == "3":
                    return model.quantization
                elif col_id == "4":
                    return "Loaded" if model.loaded else "Not Loaded"
                    
        elif table_view == self.docs_table:
            docs = list(self.suite.documents.values())
            if row < len(docs):
                doc = docs[row]
                if col_id == "0":
                    return doc.name
                elif col_id == "1":
                    return f"{doc.size_bytes / 1024 / 1024:.2f} MB"
                elif col_id == "2":
                    return str(doc.chunk_count)
                elif col_id == "3":
                    return doc.uploaded_at[:10] if doc.uploaded_at else "N/A"
        
        return ""
    
    # Button actions
    def send_message_(self, sender):
        """Send chat message."""
        message = self.input_field.string()
        if message and len(self.suite.conversations) > 0:
            conv_id = list(self.suite.conversations.keys())[0]
            result = self.suite.send_message(conv_id, message, use_rag=True)
            
            # Update chat view
            current_text = self.chat_view.string()
            new_text = f"{current_text}\n\nYou: {message}\n\nAssistant: {result['response']}"
            self.chat_view.setString_(new_text)
            self.input_field.setString_("")
    
    def load_model_(self, sender):
        """Load selected model."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Load Model")
        alert.setInformativeText_("Select a model to load")
        alert.addButtonWithTitle_("OK")
        alert.runModal()
    
    def register_model_(self, sender):
        """Register new model."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Register Model")
        alert.setInformativeText_("Enter model details")
        alert.addButtonWithTitle_("OK")
        alert.runModal()
    
    def upload_document_(self, sender):
        """Upload document for RAG."""
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Upload Document")
        alert.setInformativeText_("Select a document to upload")
        alert.addButtonWithTitle_("OK")
        alert.runModal()
    
    def refresh_analytics_(self, sender):
        """Refresh analytics display."""
        report = self.suite.get_analytics_report(days=30)
        text = json.dumps(report, indent=2)
        self.analytics_view.setString_(text)
    
    def export_suite_(self, sender):
        """Export suite for DMG packaging."""
        export_path = self.suite.export_suite("~/llm_enterprise_export")
        alert = NSAlert.alloc().init()
        alert.setMessageText_("Export Complete")
        alert.setInformativeText_(f"Suite exported to: {export_path}")
        alert.addButtonWithTitle_("OK")
        alert.runModal()
    
    def new_conversation_(self, sender):
        """Create new conversation."""
        if len(self.suite.users) > 0 and len(self.suite.models) > 0:
            user_id = list(self.suite.users.keys())[0]
            model_id = list(self.suite.models.keys())[0]
            conv = self.suite.create_conversation(user_id, model_id, "New Conversation")
            self.conv_list.reloadData()


def main():
    """Main entry point."""
    app = NSApplication.sharedApplication()
    app.setActivationPolicy_(NSApplicationActivationPolicyRegular)
    
    delegate = EnterpriseAppDelegate.alloc().init()
    app.setDelegate_(delegate)
    
    AppHelper.runEventLoop()


if __name__ == "__main__":
    main()
