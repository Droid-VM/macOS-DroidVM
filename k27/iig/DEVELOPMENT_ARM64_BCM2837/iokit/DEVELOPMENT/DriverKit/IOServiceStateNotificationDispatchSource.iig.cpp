/* iig(DriverKit-427.100.5 Apr 30 2025 01:57:02) generated from IOServiceStateNotificationDispatchSource.iig */

#undef	IIG_IMPLEMENTATION
#define	IIG_IMPLEMENTATION 	IOServiceStateNotificationDispatchSource.iig

#if KERNEL
#include <libkern/c++/OSString.h>
#else
#include <DriverKit/DriverKit.h>
#endif /* KERNEL */
#include <DriverKit/IOReturn.h>
#include <DriverKit/IOServiceStateNotificationDispatchSource.h>


#if __has_builtin(__builtin_load_member_function_pointer)
#define SimpleMemberFunctionCast(cfnty, self, func) (cfnty)__builtin_load_member_function_pointer(self, func)
#else
#define SimpleMemberFunctionCast(cfnty, self, func) OSMemberFunctionCast(cfnty, &(self), func)
#endif


struct IOServiceStateNotificationDispatchSource_Create_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  service;
    OSArray * items;
#if !defined(__LP64__)
    uint32_t __itemsPad;
#endif /* !defined(__LP64__) */
    OSObjectRef  queue;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_Create_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t service__descriptor;
    mach_msg_ool_descriptor_t  items__descriptor;
    mach_msg_port_descriptor_t queue__descriptor;
};
struct IOServiceStateNotificationDispatchSource_Create_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t service__descriptor;
    mach_msg_ool_descriptor_t  items__descriptor;
    mach_msg_port_descriptor_t queue__descriptor;
    IOServiceStateNotificationDispatchSource_Create_Msg_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_Create_Msg_ObjRefs (4)

struct IOServiceStateNotificationDispatchSource_Create_Rpl_Content
{
    IORPCMessage __hdr;
    OSObjectRef  source;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_Create_Rpl
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t source__descriptor;
};
struct IOServiceStateNotificationDispatchSource_Create_Rpl_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t source__descriptor;
    IOServiceStateNotificationDispatchSource_Create_Rpl_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_Create_Rpl_ObjRefs (1)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_Create_Msg * message;
#else /* KERNEL */
        const struct IOServiceStateNotificationDispatchSource_Create_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceStateNotificationDispatchSource_Create_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_Create_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceStateNotificationDispatchSource_Create_Invocation;
struct IOServiceStateNotificationDispatchSource_SetHandler_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_SetHandler_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOServiceStateNotificationDispatchSource_SetHandler_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOServiceStateNotificationDispatchSource_SetHandler_Msg_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_SetHandler_Msg_ObjRefs (2)

struct IOServiceStateNotificationDispatchSource_SetHandler_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_SetHandler_Rpl
{
    IORPCMessageMach           mach;
};
struct IOServiceStateNotificationDispatchSource_SetHandler_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOServiceStateNotificationDispatchSource_SetHandler_Rpl_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_SetHandler_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_SetHandler_Msg * message;
#else /* KERNEL */
        const struct IOServiceStateNotificationDispatchSource_SetHandler_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceStateNotificationDispatchSource_SetHandler_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_SetHandler_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceStateNotificationDispatchSource_SetHandler_Invocation;
struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
};
struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_ObjRefs (1)

struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl
{
    IORPCMessageMach           mach;
};
struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg * message;
#else /* KERNEL */
        const struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceStateNotificationDispatchSource_StateNotificationBegin_Invocation;
struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_Content
{
    IORPCMessage __hdr;
    OSObjectRef  __object;
    OSObjectRef  action;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
};
struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_With_Content
{
    IORPCMessageMach           mach;
    mach_msg_port_descriptor_t __object__descriptor;
    mach_msg_port_descriptor_t action__descriptor;
    IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_ObjRefs (2)

struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl_Content
{
    IORPCMessage __hdr;
};
#pragma pack(4)
struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl
{
    IORPCMessageMach           mach;
};
struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl_With_Content
{
    IORPCMessageMach           mach;
    IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl_Content content;
};
#pragma pack()
#define IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl_ObjRefs (0)


typedef union
{
    const IORPC rpc;
    struct
    {
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg * message;
#else /* KERNEL */
        const struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_With_Content * message;
#endif /* KERNEL */
        struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl_With_Content       * reply;
        uint32_t sendSize;
        uint32_t replySize;
#ifdef KERNEL
        const struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_Content * kernelContent;
#endif /* KERNEL */
    };
} IOServiceStateNotificationDispatchSource_StateNotificationReady_Invocation;
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
#endif /* !KERNEL */

#if KERNEL
OSDefineMetaClassAndStructors(IOServiceStateNotificationDispatchSource, IODispatchSource);
#endif /* KERNEL */

#if !KERNEL

#define IOServiceStateNotificationDispatchSource_QueueNames  ""

#define IOServiceStateNotificationDispatchSource_MethodNames  ""

#define IOServiceStateNotificationDispatchSourceMetaClass_MethodNames  ""

struct OSClassDescription_IOServiceStateNotificationDispatchSource_t
{
    OSClassDescription base;
    uint64_t           methodOptions[2 * 0];
    uint64_t           metaMethodOptions[2 * 0];
    char               queueNames[sizeof(IOServiceStateNotificationDispatchSource_QueueNames)];
    char               methodNames[sizeof(IOServiceStateNotificationDispatchSource_MethodNames)];
    char               metaMethodNames[sizeof(IOServiceStateNotificationDispatchSourceMetaClass_MethodNames)];
};

const struct OSClassDescription_IOServiceStateNotificationDispatchSource_t
OSClassDescription_IOServiceStateNotificationDispatchSource =
{
    .base =
    {
        .descriptionSize         = sizeof(OSClassDescription_IOServiceStateNotificationDispatchSource_t),
        .name                    = "IOServiceStateNotificationDispatchSource",
        .superName               = "IODispatchSource",
        .methodOptionsSize       = 2 * sizeof(uint64_t) * 0,
        .methodOptionsOffset     = __builtin_offsetof(struct OSClassDescription_IOServiceStateNotificationDispatchSource_t, methodOptions),
        .metaMethodOptionsSize   = 2 * sizeof(uint64_t) * 0,
        .metaMethodOptionsOffset = __builtin_offsetof(struct OSClassDescription_IOServiceStateNotificationDispatchSource_t, metaMethodOptions),
        .queueNamesSize       = sizeof(IOServiceStateNotificationDispatchSource_QueueNames),
        .queueNamesOffset     = __builtin_offsetof(struct OSClassDescription_IOServiceStateNotificationDispatchSource_t, queueNames),
        .methodNamesSize         = sizeof(IOServiceStateNotificationDispatchSource_MethodNames),
        .methodNamesOffset       = __builtin_offsetof(struct OSClassDescription_IOServiceStateNotificationDispatchSource_t, methodNames),
        .metaMethodNamesSize     = sizeof(IOServiceStateNotificationDispatchSourceMetaClass_MethodNames),
        .metaMethodNamesOffset   = __builtin_offsetof(struct OSClassDescription_IOServiceStateNotificationDispatchSource_t, metaMethodNames),
        .flags                   = 1*kOSClassCanRemote,
        .resv1                   = {0},
    },
    .methodOptions =
    {
    },
    .metaMethodOptions =
    {
    },
    .queueNames      = IOServiceStateNotificationDispatchSource_QueueNames,
    .methodNames     = IOServiceStateNotificationDispatchSource_MethodNames,
    .metaMethodNames = IOServiceStateNotificationDispatchSourceMetaClass_MethodNames,
};

OSMetaClass * gIOServiceStateNotificationDispatchSourceMetaClass;

static kern_return_t
IOServiceStateNotificationDispatchSource_New(OSMetaClass * instance);

const OSClassLoadInformation
IOServiceStateNotificationDispatchSource_Class = 
{
    .description       = &OSClassDescription_IOServiceStateNotificationDispatchSource.base,
    .metaPointer       = &gIOServiceStateNotificationDispatchSourceMetaClass,
    .version           = 1,
    .instanceSize      = sizeof(IOServiceStateNotificationDispatchSource),

    .resv2             = {0},

    .New               = &IOServiceStateNotificationDispatchSource_New,
    .resv3             = {0},

};

extern const void * const
gIOServiceStateNotificationDispatchSource_Declaration;
const void * const
gIOServiceStateNotificationDispatchSource_Declaration
__attribute__((used,visibility("hidden"),section("__DATA_CONST,__osclassinfo,regular,no_dead_strip"),no_sanitize("address")))
    = &IOServiceStateNotificationDispatchSource_Class;

static kern_return_t
IOServiceStateNotificationDispatchSource_New(OSMetaClass * instance)
{
    if (!new(instance) IOServiceStateNotificationDispatchSourceMetaClass) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

kern_return_t
IOServiceStateNotificationDispatchSourceMetaClass::New(OSObject * instance)
{
    if (!new(instance) IOServiceStateNotificationDispatchSource) return (kIOReturnNoMemory);
    return (kIOReturnSuccess);
}

#endif /* !KERNEL */

#ifdef KERNEL
#define MESSAGE_CONTENT(__field) (messageContent->__field)
#else /* KERNEL */
#define MESSAGE_CONTENT(__field) (message->content.__field)
#endif /* KERNEL */

kern_return_t
IOServiceStateNotificationDispatchSource::Dispatch(const IORPC rpc)
{
    return _Dispatch(this, rpc);
}

kern_return_t
IOServiceStateNotificationDispatchSource::_Dispatch(IOServiceStateNotificationDispatchSource * self, const IORPC rpc)
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
            ret = IODispatchSource::SetEnableWithCompletion_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::SetEnableWithCompletion_Handler, *self, &IOServiceStateNotificationDispatchSource::SetEnableWithCompletion_Impl));
            break;
        }
        case IODispatchSource_Cancel_ID:
        {
            ret = IODispatchSource::Cancel_Invoke(rpc, self, SimpleMemberFunctionCast(IODispatchSource::Cancel_Handler, *self, &IOServiceStateNotificationDispatchSource::Cancel_Impl));
            break;
        }
#if KERNEL
        case IOServiceStateNotificationDispatchSource_SetHandler_ID:
        {
            ret = IOServiceStateNotificationDispatchSource::SetHandler_Invoke(rpc, self, SimpleMemberFunctionCast(IOServiceStateNotificationDispatchSource::SetHandler_Handler, *self, &IOServiceStateNotificationDispatchSource::SetHandler_Impl));
            break;
        }
#endif /* !KERNEL */
#if KERNEL
        case IOServiceStateNotificationDispatchSource_StateNotificationBegin_ID:
        {
            ret = IOServiceStateNotificationDispatchSource::StateNotificationBegin_Invoke(rpc, self, SimpleMemberFunctionCast(IOServiceStateNotificationDispatchSource::StateNotificationBegin_Handler, *self, &IOServiceStateNotificationDispatchSource::StateNotificationBegin_Impl));
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
IOServiceStateNotificationDispatchSource::MetaClass::Dispatch(const IORPC rpc)
{
#else /* KERNEL */
kern_return_t
IOServiceStateNotificationDispatchSourceMetaClass::Dispatch(const IORPC rpc)
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
        case IOServiceStateNotificationDispatchSource_Create_ID:
            ret = IOServiceStateNotificationDispatchSource::Create_Invoke(rpc, &IOServiceStateNotificationDispatchSource::Create_Impl);
            break;
#endif /* !KERNEL */

        default:
            ret = OSMetaClassBase::Dispatch(rpc);
            break;
    }

    return (ret);
}

kern_return_t
IOServiceStateNotificationDispatchSource::Create_Call(
        IOService * service,
        OSArray * items,
        IODispatchQueue * queue,
        IOServiceStateNotificationDispatchSource ** source)
{
    kern_return_t ret;
    union
    {
        IOServiceStateNotificationDispatchSource_Create_Msg_With_Content msg;
        struct
        {
            IOServiceStateNotificationDispatchSource_Create_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOServiceStateNotificationDispatchSource_Create_Msg_With_Content * msg = &buf.msg;
    struct IOServiceStateNotificationDispatchSource_Create_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 0*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_Create_ID;
    msg->content.__object = (OSObjectRef) OSTypeID(IOServiceStateNotificationDispatchSource);
    msg->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_Create_Msg_ObjRefs;
    msg->mach.msgh_body.msgh_descriptor_count = 4;

    msg->__object__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    msg->service__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.service = (OSObjectRef) service;

    msg->items__descriptor.type = MACH_MSG_OOL_DESCRIPTOR;
    msg->items__descriptor.copy = MACH_MSG_VIRTUAL_COPY;
    msg->items__descriptor.address = (void *) __builtin_offsetof(IOServiceStateNotificationDispatchSource_Create_Msg_Content, items);
    msg->content.items = items;

    msg->queue__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;
    msg->content.queue = (OSObjectRef) queue;

#ifdef KERNEL
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl), .kernelContent = &buf.msg.content.__hdr };
#else /* KERNEL */
    IORPC rpc = { .message = &buf.msg.mach, .reply = &buf.rpl.rpl.mach, .sendSize = sizeof(buf.msg), .replySize = sizeof(buf.rpl) };
#endif /* KERNEL */
    ret = OSMTypeID(IOServiceStateNotificationDispatchSource)->Invoke(rpc);

    if (kIOReturnSuccess == ret)
    do {
        {
            if (rpl->mach.msgh.msgh_size                  != sizeof(*rpl)) { ret = kIOReturnIPCError; break; };
            if (rpl->content.__hdr.msgid                  != IOServiceStateNotificationDispatchSource_Create_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 1) { ret = kIOReturnIPCError; break; };
            if (IOServiceStateNotificationDispatchSource_Create_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
        *source = OSDynamicCast(IOServiceStateNotificationDispatchSource, (OSObject *) rpl->content.source);
        if (rpl->content.source && !*source) ret = kIOReturnBadArgument;
    }


    return (ret);
}

kern_return_t
IOServiceStateNotificationDispatchSource::SetHandler(
        OSAction * action,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOServiceStateNotificationDispatchSource_SetHandler_Msg_With_Content msg;
        struct
        {
            IOServiceStateNotificationDispatchSource_SetHandler_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOServiceStateNotificationDispatchSource_SetHandler_Msg_With_Content * msg = &buf.msg;
    struct IOServiceStateNotificationDispatchSource_SetHandler_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_SetHandler_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_SetHandler_Msg_ObjRefs;
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
            if (rpl->content.__hdr.msgid                  != IOServiceStateNotificationDispatchSource_SetHandler_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOServiceStateNotificationDispatchSource_SetHandler_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

kern_return_t
IOServiceStateNotificationDispatchSource::StateNotificationBegin(        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_With_Content msg;
        struct
        {
            IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_With_Content rpl;
            mach_msg_max_trailer_t trailer;
        } rpl;
    } buf;
    struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_With_Content * msg = &buf.msg;
    struct IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_With_Content * rpl = &buf.rpl.rpl;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 0*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_StateNotificationBegin_ID;
    msg->content.__object = (OSObjectRef) this;
    msg->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_ObjRefs;
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
            if (rpl->content.__hdr.msgid                  != IOServiceStateNotificationDispatchSource_StateNotificationBegin_ID) { ret = kIOReturnIPCError; break; };
            if (rpl->mach.msgh_body.msgh_descriptor_count != 0) { ret = kIOReturnIPCError; break; };
            if (IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_ObjRefs   != rpl->content.__hdr.objectRefs) { ret = kIOReturnIPCError; break; };
        }
    }
    while (false);
    if (kIOReturnSuccess == ret)
    {
    }


    return (ret);
}

void
IOServiceStateNotificationDispatchSource::StateNotificationReady(
        OSAction * action,
        OSDispatchMethod supermethod)
{
    kern_return_t ret;
    union
    {
        IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_With_Content msg;
    } buf;
    struct IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_With_Content * msg = &buf.msg;

    memset(msg, 0, sizeof(*msg));
    msg->mach.msgh.msgh_id   = kIORPCVersion190615;
    msg->mach.msgh.msgh_size = sizeof(*msg);
    msg->content.__hdr.flags = 1*kIORPCMessageOneway
                             | 1*kIORPCMessageSimpleReply
                             | 0*kIORPCMessageLocalHost
                             | 0*kIORPCMessageOnqueue;
    msg->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_StateNotificationReady_ID;
    msg->content.__object = (OSObjectRef) action;
    msg->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_ObjRefs;
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
IOServiceStateNotificationDispatchSource::Create_Invoke(const IORPC _rpc,
        Create_Handler func)
{
    IOServiceStateNotificationDispatchSource_Create_Invocation rpc = { _rpc };
    IOServiceStateNotificationDispatchSource_Create_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceStateNotificationDispatchSource_Create_Msg *         message = rpc.message;
    const IOServiceStateNotificationDispatchSource_Create_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceStateNotificationDispatchSource_Create_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    IOService * service;
    IODispatchQueue * queue;

    if (4 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceStateNotificationDispatchSource_Create_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceStateNotificationDispatchSource_Create_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    if (((OSObject *) MESSAGE_CONTENT(items)) != NULL && OSDynamicCast(OSArray, (OSObject *) MESSAGE_CONTENT(items)) == NULL) { return kIOReturnBadArgument; } 
    service = OSDynamicCast(IOService, (OSObject *) MESSAGE_CONTENT(service));
    if (!service && MESSAGE_CONTENT(service)) return (kIOReturnBadArgument);
    queue = OSDynamicCast(IODispatchQueue, (OSObject *) MESSAGE_CONTENT(queue));
    if (!queue && MESSAGE_CONTENT(queue)) return (kIOReturnBadArgument);

    ret = (*func)(        service,
        MESSAGE_CONTENT(items),
        queue,
        (IOServiceStateNotificationDispatchSource **)&reply->content.source);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_Create_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 1;
    reply->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_Create_Rpl_ObjRefs;
    reply->source__descriptor.type = MACH_MSG_PORT_DESCRIPTOR;

    return (ret);
}

kern_return_t
IOServiceStateNotificationDispatchSource::SetHandler_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        SetHandler_Handler func)
{
    IOServiceStateNotificationDispatchSource_SetHandler_Invocation rpc = { _rpc };
    IOServiceStateNotificationDispatchSource_SetHandler_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceStateNotificationDispatchSource_SetHandler_Msg *         message = rpc.message;
    const IOServiceStateNotificationDispatchSource_SetHandler_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceStateNotificationDispatchSource_SetHandler_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;
    OSAction * action;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceStateNotificationDispatchSource_SetHandler_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceStateNotificationDispatchSource_SetHandler_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);
    action = OSDynamicCast(OSAction, (OSObject *) MESSAGE_CONTENT(action));
    if (!action && MESSAGE_CONTENT(action)) return (kIOReturnBadArgument);

    ret = (*func)(target,
        action);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_SetHandler_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_SetHandler_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOServiceStateNotificationDispatchSource::StateNotificationBegin_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        StateNotificationBegin_Handler func)
{
    IOServiceStateNotificationDispatchSource_StateNotificationBegin_Invocation rpc = { _rpc };
    IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg *         message = rpc.message;
    const IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
#if __has_builtin(__builtin_assume)
    __builtin_assume(reply != NULL);
#endif /* __has_builtin(__builtin_assume) */
    kern_return_t ret;

    if (1 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceStateNotificationDispatchSource_StateNotificationBegin_Msg_With_Content)) return (kIOReturnIPCError);
    if (reply != NULL && rpc.replySize < sizeof(*reply)) return (kIOReturnIPCError);

    ret = (*func)(target);

    if (kIOReturnSuccess != ret) return (ret);

    reply->content.__hdr.msgid = IOServiceStateNotificationDispatchSource_StateNotificationBegin_ID;
    reply->content.__hdr.flags = kIORPCMessageOneway;
    reply->mach.msgh.msgh_id   = kIORPCVersion190615Reply;
    reply->mach.msgh.msgh_size = sizeof(*reply);
    reply->mach.msgh_body.msgh_descriptor_count = 0;
    reply->content.__hdr.objectRefs = IOServiceStateNotificationDispatchSource_StateNotificationBegin_Rpl_ObjRefs;

    return (ret);
}

kern_return_t
IOServiceStateNotificationDispatchSource::StateNotificationReady_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        StateNotificationReady_Handler func)
{
    return IOServiceStateNotificationDispatchSource::StateNotificationReady_Invoke(_rpc, target, func, NULL);
}

kern_return_t
IOServiceStateNotificationDispatchSource::StateNotificationReady_Invoke(const IORPC _rpc,
        OSMetaClassBase * target,
        StateNotificationReady_Handler func,
        const OSMetaClass * targetActionClass)
{
    IOServiceStateNotificationDispatchSource_StateNotificationReady_Invocation rpc = { _rpc };
    IOServiceStateNotificationDispatchSource_StateNotificationReady_Rpl_With_Content * reply = rpc.reply;
#ifdef KERNEL
    const IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg *         message = rpc.message;
    const IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_Content * messageContent = rpc.kernelContent;
#else /* KERNEL */
    const IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_With_Content * message = rpc.message;
#endif /* KERNEL */
    OSAction * action;

    if (2 != message->mach.msgh_body.msgh_descriptor_count) return (kIOReturnIPCError);
    if (IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_ObjRefs != MESSAGE_CONTENT(__hdr.objectRefs)) return (kIOReturnIPCError);
    if (rpc.sendSize < sizeof(IOServiceStateNotificationDispatchSource_StateNotificationReady_Msg_With_Content)) return (kIOReturnIPCError);
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



