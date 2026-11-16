/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IOServiceNotificationDispatchSource.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IOServiceNotificationDispatchSource.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IOServiceNotificationDispatchSource.h>


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IOServiceNotificationDispatchSource_Create_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSDictionary * matching;
#if !defined(__LP64__)
    uint32_t __matchingPad;
#endif /* !defined(__LP64__) */
    OSObjectRef  queue;
    uint64_t  options;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_Create_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_ool_descriptor_t  matching__descriptor;
    mach_msg_port_descriptor_t queue__descriptor;
};
struct IOServiceNotificationDispatchSource_Create_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_ool_descriptor_t  matching__descriptor;
    mach_msg_port_descriptor_t queue__descriptor;
    IOServiceNotificationDispatchSource_Create_Msg_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_Create_Msg_ObjRefs (3)

struct IOServiceNotificationDispatchSource_Create_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  notification;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_Create_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t notification__descriptor;
};
struct IOServiceNotificationDispatchSource_Create_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t notification__descriptor;
    IOServiceNotificationDispatchSource_Create_Rpl_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_Create_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_Create_Msg * message;
#else /* KERNEL */
        const struct IOServiceNotificationDispatchSource_Create_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceNotificationDispatchSource_Create_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_Create_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceNotificationDispatchSource_Create_Invocation;
struct IOServiceNotificationDispatchSource_SetHandler_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_SetHandler_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOServiceNotificationDispatchSource_SetHandler_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOServiceNotificationDispatchSource_SetHandler_Msg_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_SetHandler_Msg_ObjRefs (2)

struct IOServiceNotificationDispatchSource_SetHandler_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_SetHandler_Rpl
{
    IORPCMessageMach           mach;
};
struct IOServiceNotificationDispatchSource_SetHandler_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOServiceNotificationDispatchSource_SetHandler_Rpl_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_SetHandler_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_SetHandler_Msg * message;
#else /* KERNEL */
        const struct IOServiceNotificationDispatchSource_SetHandler_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceNotificationDispatchSource_SetHandler_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_SetHandler_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceNotificationDispatchSource_SetHandler_Invocation;
struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_ObjRefs (2)

struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl
{
    IORPCMessageMach           mach;
};
struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg * message;
#else /* KERNEL */
        const struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceNotificationDispatchSource_ServiceNotificationReady_Invocation;
struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOServiceNotificationDispatchSource_CopyNextNotification_Msg_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_CopyNextNotification_Msg_ObjRefs (1)

struct IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  service;
    unsigned long long  type;
    unsigned long long  options;
};
#pragma pack(4)
struct IOServiceNotificationDispatchSource_CopyNextNotification_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t service__descriptor;
};
struct IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t service__descriptor;
    IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_Content content;
};
#pragma pack()
#define IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg * message;
#else /* KERNEL */
        const struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceNotificationDispatchSource_CopyNextNotification_Invocation;
#if !KERNEL
extern OSMetaClass * gOSContainerMetaClass;
extern OSMetaClass * gOSDataMetaClass;
extern OSMetaClass * gOSNumberMetaClass;
extern OSMetaClass * gOSBooleanMetaClass;
extern OSMetaClass * gOSDictionaryMetaClass;
extern OSMetaClass * gOSArrayMetaClass;
extern OSMetaClass * gOSSetMetaClass;
extern OSMetaClass * gOSOrderedSetMetaClass;
extern OSMetaClass * gOSStringMetaClass;
extern OSMetaClass * gIOMemoryDescriptorMetaClass;
extern OSMetaClass * gIOBufferMemoryDescriptorMetaClass;
extern OSMetaClass * gIOUserClientMetaClass;
extern OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;
#endif /* !KERNEL */

#if KERNEL
OSDefineMetaClassAndStructors(IOServiceNotificationDispatchSource, IODispatchSource);
#endif /* KERNEL */

#if !KERNEL

#define IOServiceNotificationDispatchSource_QueueNames  ""

#define IOServiceNotificationDispatchSource_MethodNames  ""

#define IOServiceNotificationDispatchSourceMetaClass_MethodNames  ""

struct OSClassDescription_IOServiceNotificationDispatchSource_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IOServiceNotificationDispatchSource_QueueNames)];
    char               methodNames[sizeof(IOServiceNotificationDispatchSource_MethodNames)];
    char               metaMethodNames[sizeof(IOServiceNotificationDispatchSourceMetaClass_MethodNames)];
};

const struct OSClassDescription_IOServiceNotificationDispatchSource_t
OSClassDescription_IOServiceNotificationDispatchSource =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IOServiceNotificationDispatchSource_t),
        .name                    = "IOServiceNotificationDispatchSource",
        .superName               = "IODispatchSource",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IOServiceNotificationDispatchSource_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IOServiceNotificationDispatchSource_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IOServiceNotificationDispatchSource_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IOServiceNotificationDispatchSource_t, queueNames),
        .methodNamesSize         = sizeof(IOServiceNotificationDispatchSource_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IOServiceNotificationDispatchSource_t, methodNames),
        .metaMethodNamesSize     = sizeof(IOServiceNotificationDispatchSourceMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IOServiceNotificationDispatchSource_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IOServiceNotificationDispatchSource_QueueNames,
    .methodNames     = IOServiceNotificationDispatchSource_MethodNames,
    .metaMethodNames = IOServiceNotificationDispatchSourceMetaClass_MethodNames,
};

OSMetaClass * gIOServiceNotificationDispatchSourceMetaClass;

static kern_return_t
IOServiceNotificationDispatchSource_New(OSMetaClass * instance);

const OSClassLoadInformation
IOServiceNotificationDispatchSource_Class = 
{
    .description       = &OSClassDescription_IOServiceNotificationDispatchSource.base,
    .metaPointer       = &gIOServiceNotificationDispatchSourceMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IOServiceNotificationDispatchSource),

    .resv2             = {0},

    .New               = &IOServiceNotificationDispatchSource_New,
    .resv3             = {0},

};

extern const void * const
gIOServiceNotificationDispatchSource_Declaration;
const void * const
gIOServiceNotificationDispatchSource_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IOServiceNotificationDispatchSource_Class;

static kern_return_t
IOServiceNotificationDispatchSource_New(OSMetaClass * instance)
{
    if (!new(instance) IOServiceNotificationDispatchSourceMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IOServiceNotificationDispatchSourceMetaClass::New(OSObject * instance)
{
    if (!new(instance) IOServiceNotificationDispatchSource) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IOServiceNotificationDispatchSource::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IOServiceNotificationDispatchSource::_Dispatch(IOServiceNotificationDispatchSource * self, const IORPC rpc)
{
    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
        case IODispatchSource_SetEnableWithCompletion_ID:
        {
            ret = IODispatchSource::SetEnableWithCompletion_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::SetEnableWithCompletion_Handler, *self, &IOServiceNotificationDispatchSource::SetEnableWithCompletion_Impl));
            break;
        }
        case IODispatchSource_Cancel_ID:
        {
            ret = IODispatchSource::Cancel_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::Cancel_Handler, *self, &IOServiceNotificationDispatchSource::Cancel_Impl));
            break;
        }
#if KERNEL
        case IOServiceNotificationDispatchSource_SetHandler_ID:
        {
            ret = IOServiceNotificationDispatchSource::SetHandler_Invoke(rpc, self, SimpleMemberFunctionCast(IOServiceNotificationDispatchSource::SetHandler_Handler, *self, &IOServiceNotificationDispatchSource::SetHandler_Impl));
            break;
        }
#endif /* !KERNEL */
        case IODispatchSource_CheckForWork_ID:
        {
            ret = IODispatchSource::CheckForWork_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::CheckForWork_Handler, *self, &IOServiceNotificationDispatchSource::CheckForWork_Impl));
            break;
        }
#if KERNEL
        case IOServiceNotificationDispatchSource_CopyNextNotification_ID:
        {
            ret = IOServiceNotificationDispatchSource::CopyNextNotification_Invoke(rpc, self, SimpleMemberFunctionCast(IOServiceNotificationDispatchSource::CopyNextNotification_Handler, *self, &IOServiceNotificationDispatchSource::CopyNextNotification_Impl));
            break;
        }
#endif /* !KERNEL */

        default:
            ret = IODispatchSource::_Dispatch(self, rpc);
            break;
    }

    return (ret);
}

#if KERNEL
kern_return_t
IOServiceNotificationDispatchSource::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IOServiceNotificationDispatchSourceMetaClass::Dispatch(const IORPC rpc)
{
#endif /* !KERNEL */

    kern_return_t ret = kIOReturnUnsupported;
#ifdef KERNEL
    IORPCMessage * msg = rpc.kernelContent;
#else /* KERNEL */
    IORPCMessage * msg = IORPCMessageFromMach(rpc.message, false);
#endif /* KERNEL */

    switch (msg->msgid)
    {
#if KERNEL
        case IOServiceNotificationDispatchSource_Create_ID:
            ret = IOServiceNotificationDispatchSource::Create_Invoke(rpc, &IOServiceNotificationDispatchSource::Create_Impl);
            break;
#endif /* !KERNEL */

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

kern_return_t
IOServiceNotificationDispatchSource::Create_Call(
        OSDictionary * matching,
        uint64_t options,
        IODispatchQueue * queue,
        IOServiceNotificationDispatchSource ** notification)
{
    kern_return_t ret;
    union
    {
        IOServiceNotificationDispatchSource_Create_Msg_With_Content msg;
        struct
        {
            IOServiceNotificationDispatchSource_Create_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOServiceNotificationDispatchSource_Create_Msg_With_Content * msg = &buf.msg;
    struct IOServiceNotificationDispatchSource_Create_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceNotificationDispatchSource_Create_ID;
    msg->content.__object = (OSObjectRef) OSTypeID(IOServiceNotificationDispatchSource);
    msg->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_Create_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 3;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->matching__descriptor.type = MACH_MSG_OOL_DESCRIPTOR;
    msg->matching__descriptor.copy = MACH_MSG_VIRTUAL_COPY;
    msg->matching__descriptor.address = (void *) __builtin_offsetof(IOServiceNotificationDispatchSource_Create_Msg_Content, matching);
    msg->content.matching = matching;

    msg->content.options = options;

    msg->queue__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.queue = (OSObjectRef) queue;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    ret = OSMTypeID(IOServiceNotificationDispatchSource)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOServiceNotificationDispatchSource_Create_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOServiceNotificationDispatchSource_Create_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *notification = OSDynamicCast(IOServiceNotificationDispatchSource, (OSObject *) rpl->content.notification);
        if (rpl->content.notification && !*notification) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOServiceNotificationDispatchSource::SetHandler(
        OSAction * action,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOServiceNotificationDispatchSource_SetHandler_Msg_With_Content msg;
        struct
        {
            IOServiceNotificationDispatchSource_SetHandler_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOServiceNotificationDispatchSource_SetHandler_Msg_With_Content * msg = &buf.msg;
    struct IOServiceNotificationDispatchSource_SetHandler_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceNotificationDispatchSource_SetHandler_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_SetHandler_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->action__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.action = (OSObjectRef) action;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOServiceNotificationDispatchSource_SetHandler_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOServiceNotificationDispatchSource_SetHandler_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

void
IOServiceNotificationDispatchSource::ServiceNotificationReady(
        OSAction * action,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_With_Content msg;
    } buf;
    struct IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_With_Content * msg = &buf.msg;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 1*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceNotificationDispatchSource_ServiceNotificationReady_ID;
    msg->content.__object = (OSObjectRef) action;
    msg->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 2;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->action__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.action = (OSObjectRef) action;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = NULL, .sendSize = sizeof(*msg), .replySize = 0, .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = NULL, .sendSize = sizeof(*msg), .replySize = 0 };
#endif /* KERNEL */
    ret = action->Invoke(rpc);

}

kern_return_t
IOServiceNotificationDispatchSource::CopyNextNotification(
        uint64_t * type,
        IOService ** service,
        uint64_t * options,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOServiceNotificationDispatchSource_CopyNextNotification_Msg_With_Content msg;
        struct
        {
            IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOServiceNotificationDispatchSource_CopyNextNotification_Msg_With_Content * msg = &buf.msg;
    struct IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceNotificationDispatchSource_CopyNextNotification_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_CopyNextNotification_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 1;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    if (supermethod) ret = supermethod((OSObject *)this, rpc);
    else             ret = ((OSObject *)this)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOServiceNotificationDispatchSource_CopyNextNotification_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        if (type) *type = rpl->content.type;
        *service = OSDynamicCast(IOService, (OSObject *) rpl->content.service);
        if (rpl->content.service && !*service) ret = kIOReturnBadArgument;
        if (options) *options = rpl->content.options;
    }


    return (ret);
}

kern_return_t
IOServiceNotificationDispatchSource::Create_Invoke(const IORPC _rpc,
        Create_Handler func)
{
    IOServiceNotificationDispatchSource_Create_Invocation rpc = { _rpc };
    IOServiceNotificationDispatchSource_Create_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceNotificationDispatchSource_Create_Msg *         message = rpc.message;
    const IOServiceNotificationDispatchSource_Create_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceNotificationDispatchSource_Create_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IODispatchQueue * queue;

    if (3 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceNotificationDispatchSource_Create_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceNotificationDispatchSource_Create_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (((OSObject *) MESSAGE_CONTENT(matching)) != NULL && OSDynamicCast(OSDictionary, (OSObject *) MESSAGE_CONTENT(matching)) == NULL) { return kIOReturnBadArgument; } 
    queue = OSDynamicCast(IODispatchQueue, (OSObject *) MESSAGE_CONTENT(queue));
    if (!queue && MESSAGE_CONTENT(queue)) return (kIOReturnBadArgument);

    ret = (*func)(        MESSAGE_CONTENT(matching),
        MESSAGE_CONTENT(options),
        queue,
        (IOServiceNotificationDispatchSource **)&reply->content.notification);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOServiceNotificationDispatchSource_Create_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_Create_Rpl_ObjRefs;
    reply->notification__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IOServiceNotificationDispatchSource::SetHandler_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        SetHandler_Handler func)
{
    IOServiceNotificationDispatchSource_SetHandler_Invocation rpc = { _rpc };
    IOServiceNotificationDispatchSource_SetHandler_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceNotificationDispatchSource_SetHandler_Msg *         message = rpc.message;
    const IOServiceNotificationDispatchSource_SetHandler_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceNotificationDispatchSource_SetHandler_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    OSAction * action;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceNotificationDispatchSource_SetHandler_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceNotificationDispatchSource_SetHandler_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    action = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(action));
    if (!action && MESSAGE_CONTENT(action)) return (kIOReturnBadArgument);

    ret = (*func)(target,
        action);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOServiceNotificationDispatchSource_SetHandler_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_SetHandler_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOServiceNotificationDispatchSource::ServiceNotificationReady_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        ServiceNotificationReady_Handler func)
{
    return IOServiceNotificationDispatchSource::ServiceNotificationReady_Invoke(_rpc, target, func, NULL);
}

kern_return_t
IOServiceNotificationDispatchSource::ServiceNotificationReady_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        ServiceNotificationReady_Handler func,
        const OSMetaClass * targetActionClass)
{
    IOServiceNotificationDispatchSource_ServiceNotificationReady_Invocation rpc = { _rpc };
    IOServiceNotificationDispatchSource_ServiceNotificationReady_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg *         message = rpc.message;
    const IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
    OSAction * action;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceNotificationDispatchSource_ServiceNotificationReady_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (targetActionClass) {
        action = (OSAction *) OSMetaClassBase::safeMetaCast((OSObject *) MESSAGE_CONTENT(action), targetActionClass);
    } else {
        action = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(action));
    }
    if (!action && MESSAGE_CONTENT(action)) return (kIOReturnBadArgument);

    (*func)(target,
        action);


    return (kIOReturnSuccess);
}

kern_return_t
IOServiceNotificationDispatchSource::CopyNextNotification_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        CopyNextNotification_Handler func)
{
    IOServiceNotificationDispatchSource_CopyNextNotification_Invocation rpc = { _rpc };
    IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceNotificationDispatchSource_CopyNextNotification_Msg *         message = rpc.message;
    const IOServiceNotificationDispatchSource_CopyNextNotification_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceNotificationDispatchSource_CopyNextNotification_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceNotificationDispatchSource_CopyNextNotification_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceNotificationDispatchSource_CopyNextNotification_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target,
        &reply->content.type,
        (IOService **)&reply->content.service,
        &reply->content.options);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOServiceNotificationDispatchSource_CopyNextNotification_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOServiceNotificationDispatchSource_CopyNextNotification_Rpl_ObjRefs;
    reply->service__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}



